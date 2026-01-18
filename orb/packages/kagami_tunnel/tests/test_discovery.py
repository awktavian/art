"""Tests for network discovery.

Tests STUN, IP detection, and local network detection.
"""

import struct
from unittest.mock import AsyncMock, patch

import pytest

from kagami_tunnel.discovery import (
    STUN_ATTR_MAPPED_ADDRESS,
    STUN_ATTR_XOR_MAPPED_ADDRESS,
    STUN_BINDING_REQUEST,
    STUN_BINDING_RESPONSE,
    STUN_MAGIC_COOKIE,
    NATType,
    NetworkInfo,
    STUNClient,
    STUNMessage,
    discover_network,
    get_local_ip,
    is_private_ip,
    is_same_network,
)


class TestSTUNMessage:
    """Tests for STUN protocol messages."""

    def test_binding_request_creation(self):
        """Test creating a binding request."""
        msg = STUNMessage.binding_request()

        assert msg.message_type == STUN_BINDING_REQUEST
        assert len(msg.transaction_id) == 12
        assert len(msg.attributes) == 0

    def test_encode_decode_roundtrip(self):
        """Test encoding and decoding a message."""
        original = STUNMessage.binding_request()
        encoded = original.encode()
        decoded = STUNMessage.decode(encoded)

        assert decoded.message_type == original.message_type
        assert decoded.transaction_id == original.transaction_id

    def test_message_header_format(self):
        """Test message header format."""
        msg = STUNMessage.binding_request()
        encoded = msg.encode()

        # Parse header manually
        msg_type, length, magic = struct.unpack(">HHI", encoded[:8])

        assert msg_type == STUN_BINDING_REQUEST
        assert length == 0  # No attributes
        assert magic == STUN_MAGIC_COOKIE

    def test_transaction_id_uniqueness(self):
        """Test that transaction IDs are unique."""
        ids = set()
        for _ in range(100):
            msg = STUNMessage.binding_request()
            ids.add(msg.transaction_id)

        # All should be unique
        assert len(ids) == 100

    def test_xor_mapped_address_parsing(self):
        """Test parsing XOR-MAPPED-ADDRESS attribute."""
        # Create a response with XOR-MAPPED-ADDRESS
        # IP: 1.2.3.4, Port: 12345
        ip_int = (1 << 24) | (2 << 16) | (3 << 8) | 4
        port = 12345

        # XOR with magic cookie
        xored_ip = ip_int ^ STUN_MAGIC_COOKIE
        xored_port = port ^ (STUN_MAGIC_COOKIE >> 16)

        # Build attribute
        attr_data = struct.pack(">xBH", 0x01, xored_port)  # Family + XOR port
        attr_data += struct.pack(">I", xored_ip)

        msg = STUNMessage(
            message_type=STUN_BINDING_RESPONSE,
            transaction_id=b"0" * 12,
            attributes={STUN_ATTR_XOR_MAPPED_ADDRESS: attr_data},
        )

        result = msg.get_mapped_address()
        assert result is not None
        assert result[0] == "1.2.3.4"
        assert result[1] == 12345

    def test_mapped_address_parsing(self):
        """Test parsing MAPPED-ADDRESS attribute."""
        # Build attribute (unencoded)
        attr_data = struct.pack(">xBHBBBB", 0x01, 54321, 192, 168, 1, 100)

        msg = STUNMessage(
            message_type=STUN_BINDING_RESPONSE,
            transaction_id=b"0" * 12,
            attributes={STUN_ATTR_MAPPED_ADDRESS: attr_data},
        )

        result = msg.get_mapped_address()
        assert result is not None
        assert result[0] == "192.168.1.100"
        assert result[1] == 54321

    def test_invalid_message_too_short(self):
        """Test handling of too-short message."""
        with pytest.raises(ValueError, match="too short"):
            STUNMessage.decode(b"short")

    def test_invalid_magic_cookie(self):
        """Test handling of invalid magic cookie."""
        bad_data = struct.pack(">HHI", STUN_BINDING_REQUEST, 0, 0xDEADBEEF)
        bad_data += b"0" * 12  # Transaction ID

        with pytest.raises(ValueError, match="magic cookie"):
            STUNMessage.decode(bad_data)


class TestSTUNClient:
    """Tests for STUN client."""

    def test_client_creation(self):
        """Test STUN client creation."""
        client = STUNClient()

        assert len(client.servers) > 0
        assert client.timeout == 3.0

    def test_custom_servers(self):
        """Test client with custom servers."""
        servers = [("custom.stun.server", 3478)]
        client = STUNClient(servers=servers)

        assert client.servers == servers

    @pytest.mark.asyncio
    async def test_get_mapping_mock(self):
        """Test get_mapping with mocked response."""
        client = STUNClient()

        # Mock the actual request
        async def mock_request(host, port, local_port):
            return ("203.0.113.1", 54321)

        client._stun_request = mock_request

        result = await client.get_mapping()

        assert result is not None
        assert result[0] == "203.0.113.1"
        assert result[1] == 54321

    @pytest.mark.asyncio
    async def test_get_mapping_all_fail(self):
        """Test get_mapping when all servers fail."""
        client = STUNClient(servers=[("invalid.server", 1)])
        client.timeout = 0.1

        result = await client.get_mapping()

        assert result is None


class TestNATTypeDetection:
    """Tests for NAT type detection."""

    def test_nat_type_enum(self):
        """Test NAT type enumeration."""
        assert NATType.UNKNOWN.value
        assert NATType.OPEN.value
        assert NATType.FULL_CONE.value
        assert NATType.SYMMETRIC.value


class TestNetworkInfo:
    """Tests for NetworkInfo."""

    def test_needs_tunnel_symmetric(self):
        """Test tunnel requirement for symmetric NAT."""
        info = NetworkInfo(
            local_ip="192.168.1.100",
            nat_type=NATType.SYMMETRIC,
        )

        assert info.needs_tunnel()

    def test_needs_tunnel_unknown(self):
        """Test tunnel requirement for unknown NAT."""
        info = NetworkInfo(
            local_ip="192.168.1.100",
            nat_type=NATType.UNKNOWN,
        )

        assert info.needs_tunnel()

    def test_no_tunnel_cone_nat(self):
        """Test no tunnel needed for cone NAT."""
        info = NetworkInfo(
            local_ip="192.168.1.100",
            nat_type=NATType.FULL_CONE,
        )

        assert not info.needs_tunnel()

    def test_supports_hole_punch(self):
        """Test hole punch support detection."""
        # Cone NAT supports hole punch
        info = NetworkInfo(
            local_ip="192.168.1.100",
            nat_type=NATType.PORT_RESTRICTED_CONE,
        )
        assert info.supports_hole_punch()

        # Symmetric doesn't
        info.nat_type = NATType.SYMMETRIC
        assert not info.supports_hole_punch()


class TestIPAddressHelpers:
    """Tests for IP address helper functions."""

    def test_is_private_ip_rfc1918(self):
        """Test RFC 1918 private IP detection."""
        # 10.0.0.0/8
        assert is_private_ip("10.0.0.1")
        assert is_private_ip("10.255.255.255")

        # 172.16.0.0/12
        assert is_private_ip("172.16.0.1")
        assert is_private_ip("172.31.255.255")

        # 192.168.0.0/16
        assert is_private_ip("192.168.0.1")
        assert is_private_ip("192.168.255.255")

    def test_is_not_private_ip(self):
        """Test public IP detection."""
        assert not is_private_ip("8.8.8.8")
        assert not is_private_ip("1.1.1.1")
        assert not is_private_ip("142.250.80.46")  # google.com

    def test_is_private_ip_localhost(self):
        """Test localhost detection."""
        assert is_private_ip("127.0.0.1")
        assert is_private_ip("127.0.0.255")

    def test_is_private_ip_invalid(self):
        """Test invalid IP handling."""
        assert not is_private_ip("invalid")
        assert not is_private_ip("")

    def test_is_same_network(self):
        """Test same network detection."""
        assert is_same_network("192.168.1.1", "192.168.1.100")
        assert is_same_network("192.168.1.1", "192.168.1.254")

    def test_is_different_network(self):
        """Test different network detection."""
        assert not is_same_network("192.168.1.1", "192.168.2.1")
        assert not is_same_network("10.0.0.1", "192.168.1.1")

    def test_is_same_network_custom_prefix(self):
        """Test same network with custom prefix length."""
        # /16 - same network
        assert is_same_network("192.168.1.1", "192.168.2.1", prefix_len=16)

        # /24 - different network
        assert not is_same_network("192.168.1.1", "192.168.2.1", prefix_len=24)

    def test_is_same_network_invalid(self):
        """Test invalid IP handling in same_network."""
        assert not is_same_network("invalid", "192.168.1.1")
        assert not is_same_network("192.168.1.1", "invalid")


class TestLocalIPDetection:
    """Tests for local IP detection."""

    @pytest.mark.asyncio
    async def test_get_local_ip(self):
        """Test local IP detection."""
        ip = await get_local_ip()

        # Should return something valid
        assert ip is not None
        assert len(ip) > 0

        # If not loopback, should be private
        if ip != "127.0.0.1":
            assert is_private_ip(ip)


class TestNetworkDiscovery:
    """Tests for full network discovery."""

    @pytest.mark.asyncio
    async def test_discover_network_mock(self):
        """Test network discovery with mocked STUN."""
        with patch.object(STUNClient, "get_mapping", new_callable=AsyncMock) as mock_mapping:
            with patch.object(STUNClient, "detect_nat_type", new_callable=AsyncMock) as mock_nat:
                mock_mapping.return_value = ("203.0.113.1", 54321)
                mock_nat.return_value = NATType.PORT_RESTRICTED_CONE

                info = await discover_network()

                assert info.external_ip == "203.0.113.1"
                assert info.external_port == 54321
                assert info.nat_type == NATType.PORT_RESTRICTED_CONE
                assert info.local_ip is not None
