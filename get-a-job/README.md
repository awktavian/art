# Get A Job 💼

**The Sequel to [Boss Your Car Around](../boss-your-car.html)**

> "Tell the robots to get a job" — Kristi Jacoby

## Overview

This interactive article explains Kagami's economic autonomy system — how an AI agent can participate in markets, make Pareto optimal decisions, and learn from outcomes.

## The Economic Model

Kagami uses **Active Inference** with Expected Free Energy (EFE) for economic decision making:

```
EFE(a) = E[revenue] − λ·risk − cost(a) + info_gain
```

Where:
- **E[revenue]** — Expected payment based on Bayesian market models
- **λ·risk** — Risk-weighted probability of failure
- **cost(a)** — Compute time, API calls, opportunity cost
- **info_gain** — Learning value (reduces future uncertainty)

## Key Systems

### 1. Economic Sensors (`kagami.core.integrations.sensory.economic`)
- Poll Freelancer jobs in real-time
- Track plugin marketplace demand
- Monitor pricing signals
- Assess available capacity

### 2. Economic Effectors (`kagami.core.economic.economic_effectors`)
- `BidSubmissionEffector` — Submit bids on freelance platforms
- `PricingEffector` — Adjust marketplace plugin prices
- `CapabilityPublisher` — Advertise skills to marketplaces

### 3. Revenue Learning Loop (`kagami.core.economic.revenue_learning`)
- Bayesian updating of market models (alpha/beta for success rates)
- Skill-specific success rate and hourly rate learning
- Dynamic risk tolerance adjustment
- Persistent outcome storage for long-term learning

### 4. Autonomous Goal Engine (`kagami.core.autonomous_goal_engine`)
- Active Inference loop with economic perception
- EFE-based action selection
- Automatic learning from outcomes
- Cross-domain trigger integration

## Pareto Optimal Choices

The interactive visualization shows how jobs are evaluated:
- **Green frontier** — Pareto optimal choices (no strictly better option)
- **Job size** — Proportional to EFE score
- **Color** — Green (high EFE), Gold (medium), Orange (low)

## Live Demo

Visit: https://awktavian.github.io/art/get-a-job/

## Technical Stack

- Single-page HTML with embedded CSS/JS
- Canvas-based Pareto frontier visualization
- No build step required
- IBM Plex Sans typography
- Fibonacci timing (144ms, 233ms, 377ms)
- Money-themed color palette (green/gold)

## Connection to Boss Your Car

Both articles demonstrate Kagami's **autonomous agency**:
- **Boss Your Car** — Physical world control (Tesla API)
- **Get A Job** — Economic world participation (Freelancer, Stripe)

The pattern is the same:
1. **Sense** the environment (weather/market)
2. **Decide** using EFE optimization
3. **Act** through effectors (climate control/bid submission)
4. **Learn** from outcomes

## Files

```
get-a-job/
├── index.html      # Main article (self-contained)
└── README.md       # This file
```

## Credits

- Inspiration: Kristi Jacoby
- Design System: Kagami Art Guidelines
- Implementation: Kagami Economic Agent Team

---

*"Money is just frozen time."*
