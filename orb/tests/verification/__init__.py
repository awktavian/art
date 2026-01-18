"""Verification tests for scientific claims.

This module contains tests that verify the core scientific claims made about
Kagami OS. All tests follow the verification protocol in:
docs/SCIENTIFIC_VERIFICATION_PROTOCOL.md

Crystal's domain: Comprehensive verification of all system improvements.

This package contains end-to-end verification tests that prove:
1. Correctness: Components do what they claim
2. Safety: No invariant violations possible
3. Performance: Meets latency/throughput requirements
4. Integration: Components work together

Test Categories:
- E8 Optimality: E8 lattice vs. baselines (learned codebooks, random lattices)
- CBF Safety: Adversarial testing, fuzzing, formal verification
- Fano Routing: Latency, message overhead, quality degradation
- Statistical Power: Sample size validation, power analysis

Each test is marked with:
- @pytest.mark.verification: Indicates verification test
- @pytest.mark.slow: Long-running tests (minutes to hours)
- @pytest.mark.statistical: Requires statistical validation

Run with:
    make test-verification  # All verification tests
    pytest tests/verification/ -m "not slow"  # Fast tests only
    pytest tests/verification/test_e8_optimality.py -v  # Specific claim

Created: December 14, 2025
"""
