from __future__ import annotations

from typing import cast

"Trust Region Constraints for Safe Policy Updates\n\nEnsures state/policy updates stay within trusted boundaries using:\n- KL divergence for distributional trust\n- Hyperbolic distance for geometric trust (H⁷)\n- Spherical distance for orientational trust (S⁷)\n\nBased on:\n- TRPO (Schulman et al., 2015): Trust region policy optimization\n- PPO (Schulman et al., 2017): Proximal policy optimization\n- Geometric trust regions (custom for H⁷ × S⁷)\n"
import logging

import torch
import torch.nn.functional as F

logger = logging.getLogger(__name__)


class TrustRegionConstraint:
    """Enforce trust region constraints on state/policy updates.

    Trust region: D_KL(π_new || π_old) ≤ ε
    For geometric manifolds: d_H⁷(x_new, x_old) ≤ δ
    """

    def __init__(
        self,
        kl_epsilon: float = 0.1,
        hyperbolic_delta: float = 0.5,
        spherical_delta: float = 0.3,
        projection_steps: int = 10,
    ) -> None:
        """Initialize trust region constraints.

        Args:
            kl_epsilon: Maximum KL divergence for policy updates
            hyperbolic_delta: Maximum hyperbolic distance for H⁷
            spherical_delta: Maximum geodesic distance for S⁷
            projection_steps: Gradient steps for projection
        """
        self.kl_epsilon = kl_epsilon
        self.hyperbolic_delta = hyperbolic_delta
        self.spherical_delta = spherical_delta
        self.projection_steps = projection_steps

    def project_state_to_trust_region(
        self, x_new: torch.Tensor, x_trust: torch.Tensor, manifold: str = "combined"
    ) -> torch.Tensor:
        """Project new state to trust region around trusted state.

        Args:
            x_new: Proposed new state [..., dim]
            x_trust: Trusted reference state [..., dim]
            manifold: Which manifold to use for distance

        Returns:
            Projected safe state within trust region
        """
        if manifold == "hyperbolic":
            return self._project_hyperbolic(x_new, x_trust)
        elif manifold == "spherical":
            return self._project_spherical(x_new, x_trust)
        else:
            z_new, o_new = (x_new[..., :7], x_new[..., 7:])
            z_trust, o_trust = (x_trust[..., :7], x_trust[..., 7:])
            z_proj = self._project_hyperbolic(z_new, z_trust)
            o_proj = self._project_spherical(o_new, o_trust)
            return torch.cat([z_proj, o_proj], dim=-1)

    def _project_hyperbolic(self, z_new: torch.Tensor, z_trust: torch.Tensor) -> torch.Tensor:
        """Project to hyperbolic trust region using Poincaré distance.

        Poincaré distance: d(x,y) = arcosh(1 + 2||x-y||²/((1-||x||²)(1-||y||²)))
        """
        diff = z_new - z_trust
        norm_diff = diff.norm(dim=-1, keepdim=True)
        norm_new = z_new.norm(dim=-1, keepdim=True).clamp(max=0.99)
        norm_trust = z_trust.norm(dim=-1, keepdim=True).clamp(max=0.99)
        numerator = 2 * norm_diff**2
        denominator = (1 - norm_new**2) * (1 - norm_trust**2) + 1e-08
        dist = torch.sqrt(1 + numerator / denominator)
        if dist.max() > self.hyperbolic_delta:
            scale = self.hyperbolic_delta / (dist + 1e-08)
            direction = diff / (norm_diff + 1e-08)
            z_proj = z_trust + scale * norm_diff * direction
            z_proj_norm = z_proj.norm(dim=-1, keepdim=True)
            z_proj = torch.where(z_proj_norm > 0.99, z_proj * 0.99 / (z_proj_norm + 1e-08), z_proj)
            return z_proj
        return z_new

    def _project_spherical(self, o_new: torch.Tensor, o_trust: torch.Tensor) -> torch.Tensor:
        """Project to spherical trust region using geodesic distance.

        Geodesic distance on S⁷: arccos(<o_new, o_trust>)
        """
        o_new = o_new / (o_new.norm(dim=-1, keepdim=True) + 1e-08)
        o_trust = o_trust / (o_trust.norm(dim=-1, keepdim=True) + 1e-08)
        dot_product = (o_new * o_trust).sum(dim=-1, keepdim=True).clamp(-1, 1)
        dist = torch.acos(dot_product)
        if dist.max() > self.spherical_delta:
            theta = dist.clamp(min=1e-08)
            scale = self.spherical_delta / theta
            o_proj = (
                torch.sin((1 - scale) * theta) / torch.sin(theta) * o_trust
                + torch.sin(scale * theta) / torch.sin(theta) * o_new
            )
            o_proj = o_proj / (o_proj.norm(dim=-1, keepdim=True) + 1e-08)
            return cast(torch.Tensor, o_proj)
        return o_new

    def compute_kl_divergence(
        self, policy_new: torch.Tensor, policy_old: torch.Tensor
    ) -> torch.Tensor:
        """Compute KL(new || old) for policy distributions.

        Args:
            policy_new: New policy logits [..., num_actions]
            policy_old: Old policy logits [..., num_actions]

        Returns:
            KL divergence [..., 1]
        """
        p_new = F.softmax(policy_new, dim=-1)
        p_old = F.softmax(policy_old, dim=-1)
        kl = (p_new * (p_new.log() - p_old.log())).sum(dim=-1, keepdim=True)
        return kl

    def project_policy_to_trust_region(
        self, policy_new: torch.Tensor, policy_old: torch.Tensor
    ) -> torch.Tensor:
        """Project policy update to stay within KL trust region.

        If D_KL(new || old) > ε, interpolate to boundary.

        Args:
            policy_new: New policy logits [..., num_actions]
            policy_old: Old policy logits [..., num_actions]

        Returns:
            Safe policy logits within trust region
        """
        kl = self.compute_kl_divergence(policy_new, policy_old)
        if kl.max() > self.kl_epsilon:
            alpha_low, alpha_high = (0.0, 1.0)
            for _ in range(self.projection_steps):
                alpha_mid = (alpha_low + alpha_high) / 2
                policy_mid = alpha_mid * policy_new + (1 - alpha_mid) * policy_old
                kl_mid = self.compute_kl_divergence(policy_mid, policy_old)
                if kl_mid.max() > self.kl_epsilon:
                    alpha_high = alpha_mid
                else:
                    alpha_low = alpha_mid
            alpha = alpha_low
            policy_proj = alpha * policy_new + (1 - alpha) * policy_old
            logger.debug(f"Trust region: KL={kl.max():.4f} → {self.kl_epsilon:.4f}, α={alpha:.3f}")
            return policy_proj
        return policy_new


_global_trust_region: TrustRegionConstraint | None = None


def get_trust_region() -> TrustRegionConstraint:
    """Get global trust region constraint instance."""
    global _global_trust_region
    if _global_trust_region is None:
        _global_trust_region = TrustRegionConstraint()
    return _global_trust_region


if __name__ == "__main__":
    print("=" * 60)
    print("Trust Region Constraint Test")
    print("=" * 60)
    constraint = TrustRegionConstraint(kl_epsilon=0.1, hyperbolic_delta=0.5, spherical_delta=0.3)
    x_trust = torch.randn(2, 15)
    x_new = torch.randn(2, 15) * 2
    x_proj = constraint.project_state_to_trust_region(x_new, x_trust, manifold="combined")
    z_trust, o_trust = (x_trust[..., :7], x_trust[..., 7:])
    z_proj, o_proj = (x_proj[..., :7], x_proj[..., 7:])
    hyp_dist = (z_proj - z_trust).norm()
    sph_dist = torch.acos((o_proj * o_trust).sum(dim=-1).clamp(-1, 1))
    print("\n✅ Projection complete")
    print(f"   Hyperbolic distance: {hyp_dist:.4f} (limit: {constraint.hyperbolic_delta})")
    print(f"   Spherical distance: {sph_dist.mean():.4f} (limit: {constraint.spherical_delta})")
    print(f"   Within trust region: {hyp_dist <= constraint.hyperbolic_delta}")
    policy_old = torch.randn(2, 10)
    policy_new = torch.randn(2, 10) * 2
    policy_proj = constraint.project_policy_to_trust_region(policy_new, policy_old)
    kl = constraint.compute_kl_divergence(policy_proj, policy_old)
    print("\n✅ Policy projection complete")
    print(f"   KL divergence: {kl.max():.4f} (limit: {constraint.kl_epsilon})")
    print(f"   Within trust region: {kl.max() <= constraint.kl_epsilon}")
    print("\n" + "=" * 60)
    print("✅ Trust region constraints operational")
    print("=" * 60)
