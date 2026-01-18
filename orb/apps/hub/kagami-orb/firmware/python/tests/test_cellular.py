"""
Tests for Cellular Modem Driver

Tests cover:
- Modem initialization and AT commands
- Signal quality parsing
- Network registration
- Data connection management
- SMS functionality
"""

import pytest
from datetime import datetime

import sys
sys.path.insert(0, str(pytest.importorskip("pathlib").Path(__file__).parent.parent))

from kagami_orb.drivers.cellular import (
    CellularModem,
    ModemManager,
    ModemInfo,
    SignalQuality,
    CellInfo,
    NetworkType,
    RegistrationStatus,
    SIMStatus,
    ConnectionState,
)


class TestEnums:
    """Test enum definitions."""
    
    def test_network_types(self):
        """Test network type values."""
        assert NetworkType.LTE.value == "lte"
        assert NetworkType.NR5G_SA.value == "nr5g_sa"
        assert NetworkType.GSM.value == "gsm"
    
    def test_registration_status(self):
        """Test registration status values."""
        assert RegistrationStatus.NOT_REGISTERED == 0
        assert RegistrationStatus.REGISTERED_HOME == 1
        assert RegistrationStatus.REGISTERED_ROAMING == 5
    
    def test_sim_status(self):
        """Test SIM status values."""
        assert SIMStatus.READY.value == "ready"
        assert SIMStatus.PIN_REQUIRED.value == "pin_required"


class TestSignalQuality:
    """Test SignalQuality dataclass."""
    
    def test_quality_percent_strong(self):
        """Test quality percentage for strong signal."""
        sq = SignalQuality(
            rssi_dbm=-51,
            rsrp_dbm=-80,
            rsrq_db=-10,
            sinr_db=20,
            ber=0,
            bars=5,
        )
        assert sq.quality_percent == 100
    
    def test_quality_percent_weak(self):
        """Test quality percentage for weak signal."""
        sq = SignalQuality(
            rssi_dbm=-113,
            rsrp_dbm=-140,
            rsrq_db=-20,
            sinr_db=-20,
            ber=99,
            bars=0,
        )
        assert sq.quality_percent == 0
    
    def test_quality_percent_mid(self):
        """Test quality percentage for mid-range signal."""
        sq = SignalQuality(
            rssi_dbm=-82,
            rsrp_dbm=-100,
            rsrq_db=-12,
            sinr_db=10,
            ber=1,
            bars=3,
        )
        # (-82 + 113) / 62 * 100 = 50%
        assert 45 <= sq.quality_percent <= 55


class TestCellularModem:
    """Test cellular modem driver."""
    
    @pytest.fixture
    def modem(self):
        """Create modem in simulation mode."""
        return CellularModem(simulate=True)
    
    def test_initialization(self, modem):
        """Test modem initializes correctly."""
        assert modem.is_initialized()
    
    def test_get_modem_info(self, modem):
        """Test getting modem identification."""
        info = modem.get_modem_info()
        
        assert isinstance(info, ModemInfo)
        assert info.manufacturer == "Quectel"
        assert info.model == "EG25-G"
        assert len(info.imei) == 15
    
    def test_get_sim_status(self, modem):
        """Test SIM status check."""
        status = modem.get_sim_status()
        
        assert status == SIMStatus.READY
    
    def test_get_signal_quality(self, modem):
        """Test signal quality reading."""
        sq = modem.get_signal_quality()
        
        assert isinstance(sq, SignalQuality)
        assert -113 <= sq.rssi_dbm <= -51 or sq.rssi_dbm == -999
        assert 0 <= sq.bars <= 5
    
    def test_get_registration_status(self, modem):
        """Test network registration status."""
        status, cell_info = modem.get_registration_status()
        
        assert status in [RegistrationStatus.REGISTERED_HOME, RegistrationStatus.REGISTERED_ROAMING]
    
    def test_connect(self, modem):
        """Test data connection establishment."""
        success = modem.connect()
        
        assert success
        assert modem.get_connection_state() == ConnectionState.CONNECTED
    
    def test_disconnect(self, modem):
        """Test data connection termination."""
        modem.connect()
        success = modem.disconnect()
        
        assert success
        assert modem.get_connection_state() == ConnectionState.DISCONNECTED
    
    def test_is_connected(self, modem):
        """Test connection check."""
        assert not modem.is_connected()
        
        modem.connect()
        assert modem.is_connected()
    
    def test_send_sms(self, modem):
        """Test SMS sending."""
        success = modem.send_sms("+15551234567", "Test message")
        
        assert success
    
    def test_enable_gnss(self, modem):
        """Test enabling integrated GNSS."""
        success = modem.enable_gnss()
        
        assert success
    
    def test_disable_gnss(self, modem):
        """Test disabling integrated GNSS."""
        modem.enable_gnss()
        success = modem.disable_gnss()
        
        assert success


class TestATCommandSimulation:
    """Test AT command simulation."""
    
    @pytest.fixture
    def modem(self):
        return CellularModem(simulate=True)
    
    def test_at_command(self, modem):
        """Test basic AT command."""
        success, lines = modem._send_command("AT")
        
        assert success
        assert "OK" in lines
    
    def test_csq_command(self, modem):
        """Test CSQ (signal quality) command."""
        success, lines = modem._send_command("AT+CSQ")
        
        assert success
        assert any("+CSQ:" in line for line in lines)
    
    def test_cops_command(self, modem):
        """Test COPS (operator) command."""
        success, lines = modem._send_command("AT+COPS?")
        
        assert success
        assert any("+COPS:" in line for line in lines)
    
    def test_cpin_command(self, modem):
        """Test CPIN (SIM status) command."""
        success, lines = modem._send_command("AT+CPIN?")
        
        assert success
        assert any("READY" in line for line in lines)


class TestModemManager:
    """Test modem manager."""
    
    @pytest.fixture
    def manager(self):
        return ModemManager(simulate=True)
    
    def test_initialization(self, manager):
        """Test manager initializes modem."""
        assert manager.modem.is_initialized()
    
    @pytest.mark.asyncio
    async def test_start_stop(self, manager):
        """Test starting and stopping manager."""
        await manager.start()
        
        assert manager._running
        
        await manager.stop()
        
        assert not manager._running
    
    def test_get_signal_quality(self, manager):
        """Test signal quality retrieval."""
        # Need to start for monitoring
        # In this test, just check direct access
        sq = manager.modem.get_signal_quality()
        
        assert sq is not None
    
    def test_is_connected(self, manager):
        """Test connection status check."""
        assert not manager.is_connected()
        
        manager.modem.connect()
        assert manager.is_connected()


class TestNetworkTypes:
    """Test network type detection."""
    
    def test_network_type_mapping(self):
        """Test network type enum values."""
        assert NetworkType.GSM.value == "gsm"
        assert NetworkType.LTE.value == "lte"
        assert NetworkType.NR5G_SA.value == "nr5g_sa"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
