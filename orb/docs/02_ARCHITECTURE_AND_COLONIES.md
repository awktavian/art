# Architecture and Colonies

*Seven minds, one system. Mathematical elegance in cognitive architecture.*

---

## Executive Summary

Kagami's cognitive architecture is built on **seven specialized colonies** that coordinate through the **Fano plane**---the smallest finite projective geometry. Events flow through an **E8 lattice event bus** that provides 240 routing channels partitioned across the colonies. Each colony embodies an **elementary catastrophe** from Thom's classification, giving the system mathematically principled phase transitions.

This is not metaphor. The math is real. The geometry is implemented.

---

## The Seven Colonies

```
                         SPARK (1)
                          /|\
                         / | \
                        /  |  \
                       /   |   \
                 NEXUS(4)--+---FORGE(2)
                    / \   |   / \
                   /   \  |  /   \
                  /     \ | /     \
           GROVE(6)---CRYSTAL(7)---FLOW(3)---BEACON(5)
```

Each colony is a specialized cognitive unit:

| Colony | Index | Role | Catastrophe | What It Does |
|--------|-------|------|-------------|--------------|
| **Spark** | 1 | Igniter | Fold (A2) | Generate ideas, brainstorm, imagine possibilities |
| **Forge** | 2 | Builder | Cusp (A3) | Implement features, execute plans, transform inputs |
| **Flow** | 3 | Healer | Swallowtail (A4) | Debug issues, recover from errors, maintain health |
| **Nexus** | 4 | Bridge | Butterfly (A5) | Connect systems, integrate data, manage memory |
| **Beacon** | 5 | Architect | Hyperbolic (D4+) | Plan strategies, schedule tasks, orchestrate workflows |
| **Grove** | 6 | Scholar | Elliptic (D4-) | Research solutions, document knowledge, explore options |
| **Crystal** | 7 | Judge | Parabolic (D5) | Verify correctness, audit quality, validate outputs |

---

## Why Seven? The Fano Plane

The Fano plane is the smallest projective plane over a finite field (F2). It has exactly:
- **7 points** (our colonies)
- **7 lines** (composition rules)
- **3 points per line** (natural team size)
- **3 lines through each point** (each colony has 3 collaboration pathways)

```
    THE FANO PLANE
    ==============

         1
        /|\
       / | \
      /  |  \
     4---7---2
    / \ /|\ / \
   /   X | X   \
  /   / \|/ \   \
 6-------3-------5

 Lines (each contains exactly 3 points):

 Line A: {1, 2, 3}  The center vertical from 1 through 7 to 3
 Line B: {1, 4, 5}  The left side down from 1 through 4 to 5
 Line C: {1, 7, 6}  From 1 through center (7) to 6
 Line D: {2, 4, 6}  From 2 through 4 to 6
 Line E: {2, 5, 7}  From 2 down to 5 through center
 Line F: {3, 4, 7}  From 3 through 4 to center
 Line G: {3, 5, 6}  The bottom from 3 through 5 to 6
```

### Why This Matters

The Fano plane is the multiplication table of the **imaginary octonions**---a 7-dimensional algebra. When Colony A works with Colony B, the Fano line tells you which Colony C naturally completes their work:

```
Spark x Forge = Flow       Create something, build it, debug it
Spark x Nexus = Beacon     Create something, connect it, plan it
Spark x Crystal = Grove    Create something, verify it, research it
Forge x Nexus = Grove      Build something, connect it, research it
Forge x Beacon = Crystal   Build something, plan it, verify it
Flow x Nexus = Crystal     Debug something, connect it, verify it
Flow x Grove = Beacon      Debug something, research it, plan it
```

This is **not arbitrary**. The algebra determines the collaboration.

---

## Catastrophe Theory Foundation

Each colony corresponds to one of Thom's seven elementary catastrophes. These are the only stable ways a smooth system can undergo discontinuous change:

### A-Series (Cuspoid Catastrophes)

```
FOLD (A2) - Spark
===================
Potential: x^3
Control: 1 parameter
Behavior: Sudden jump from one state to another

             |
         ____/
        /        <- creative leap
    ___/
   |

CUSP (A3) - Forge
===================
Potential: x^4
Control: 2 parameters
Behavior: Bistability, hysteresis

          /\
         /  \
        /    \     <- can be in either stable state
    ___/      \___

SWALLOWTAIL (A4) - Flow
========================
Potential: x^5
Control: 3 parameters
Behavior: Three-way branching, recovery paths

         /\
        /  \
       / /\ \      <- multiple recovery pathways
    __/ /  \ \__

BUTTERFLY (A5) - Nexus
=======================
Potential: x^6
Control: 4 parameters
Behavior: Complex bridging between states

       /\  /\
      /  \/  \     <- connecting disparate states
    _/   ||   \_
```

### D-Series (Umbilic Catastrophes)

```
HYPERBOLIC UMBILIC (D4+) - Beacon
==================================
Potential: x^3 + y^3
Behavior: Overview, seeing the whole landscape

    \   |   /
     \  |  /       <- panoramic view
      \ | /
    ----+----

ELLIPTIC UMBILIC (D4-) - Grove
===============================
Potential: x^3 - xy^2
Behavior: Depth, focused investigation

        /|\
       / | \       <- drilling deep
      /  |  \
     /   |   \

PARABOLIC UMBILIC (D5) - Crystal
=================================
Potential: x^2y + y^4
Control: Highest complexity
Behavior: Critical judgment, stability analysis

       ___
      /   \        <- weighing, judging
     /  ?  \
    /_______\
```

### Why Catastrophe Theory?

Cognitive systems undergo phase transitions. Ideas crystallize suddenly (fold). Decisions flip between options (cusp). Recovery from errors follows branching paths (swallowtail). The math isn't decoration---it describes how each colony *should* behave during state changes.

---

## E8 Lattice Event Bus

All inter-colony communication flows through the **Unified E8 Event Bus**.

### What is E8?

E8 is an 8-dimensional lattice with remarkable properties:
- **240 minimal vectors** (roots)---all the same length
- **Densest sphere packing** in 8 dimensions
- **Exceptional symmetry** (Weyl group of order 696,729,600)
- **Contains Fano structure**---7 partitions for 7 colonies

```
E8 LATTICE STRUCTURE
====================

Dimension: 8
Kissing Number: 240 (each point touches 240 neighbors)
Minimal Vectors: 240 roots, partitioned across colonies

     Colony 1 (Spark)   : Roots 0-33    (34 roots)
     Colony 2 (Forge)   : Roots 34-67   (34 roots)
     Colony 3 (Flow)    : Roots 68-101  (34 roots)
     Colony 4 (Nexus)   : Roots 102-135 (34 roots)
     Colony 5 (Beacon)  : Roots 136-169 (34 roots)
     Colony 6 (Grove)   : Roots 170-203 (34 roots)
     Colony 7 (Crystal) : Roots 204-239 (36 roots)
                                        --------
                               Total:   240 roots
```

### Semantic Topic Routing

Topics map to colonies by semantic prefix:

```
Topic Prefix    Colony      E8 Root Range
============    ======      =============
create.*        Spark       0-33
generate.*      Spark       0-33
brainstorm.*    Spark       0-33

build.*         Forge       34-67
implement.*     Forge       34-67
execute.*       Forge       34-67

debug.*         Flow        68-101
fix.*           Flow        68-101
recover.*       Flow        68-101

memory.*        Nexus       102-135
connect.*       Nexus       102-135
integrate.*     Nexus       102-135

plan.*          Beacon      136-169
schedule.*      Beacon      136-169
orchestrate.*   Beacon      136-169

research.*      Grove       170-203
search.*        Grove       170-203
document.*      Grove       170-203

test.*          Crystal     204-239
verify.*        Crystal     204-239
audit.*         Crystal     204-239
```

### Event Structure

```
+------------------------------------------------------------------+
|                         E8 EVENT                                   |
+------------------------------------------------------------------+
| topic          : string       "build.feature.login"               |
| payload        : dict         {"name": "login", "priority": 1}    |
| token          : E8Token      DATA | QUERY | BROADCAST | FANO     |
| source_colony  : int          2 (Forge)                           |
| target_colony  : int          -1 (broadcast) or specific colony   |
| e8_index       : int          45 (specific E8 root)               |
| fano_route     : list[int]    [1, 2, 3] (Fano line colonies)      |
| timestamp      : float        1735689600.123                      |
| id             : string       "evt_abc123xyz"                     |
+------------------------------------------------------------------+
```

### Control Tokens

| Token | Hex | Purpose |
|-------|-----|---------|
| DATA | 0x02 | Normal data event |
| QUERY | 0x03 | Memory query request |
| BROADCAST | 0x05 | Send to all colonies |
| FANO | 0x06 | Route via Fano line (3 colonies) |
| SYNC | 0x07 | Synchronization checkpoint |
| EXPERIENCE | 0x10 | Learning outcome |
| APP_EVENT | 0x11 | Application-level event |
| CHARACTER | 0x12 | Character/personality feedback |

---

## Request Flow: From Input to Output

Here's how a request flows through the system:

```
+-------------------------------------------------------------------------+
|                        REQUEST FLOW DIAGRAM                              |
+-------------------------------------------------------------------------+

User Request: "Fix the bug in the payment system"
                              |
                              v
+------------------------------|--------------------------------------+
|                    FANO ACTION ROUTER                                |
|                              |                                       |
|  1. Parse Intent             |                                       |
|     Keywords: "fix", "bug"   ---> Flow (debugging)                   |
|     Domain: "payment"        ---> Forge (building)                   |
|                              |                                       |
|  2. Fano Lookup              |                                       |
|     Flow (3) + Forge (2)     ---> Line {1,2,3}                       |
|     Third colony: Spark (1)  |                                       |
|                              |                                       |
|  3. Activate 3 Colonies      |                                       |
|     [Spark, Forge, Flow]     |                                       |
+------------------------------|--------------------------------------+
                              |
                              v
+------------------------------|--------------------------------------+
|                    E8 EVENT BUS                                      |
|                              |                                       |
|  Publish: topic="debug.payment.fix"                                  |
|           token=FANO                                                 |
|           fano_route=[1,2,3]                                         |
|           e8_index=72 (Flow partition)                               |
|                              |                                       |
|            +--------+--------+--------+                              |
|            |        |                 |                              |
|            v        v                 v                              |
|         Spark    Forge             Flow                              |
|         (e1)     (e2)              (e3)                              |
+------------------------------|--------------------------------------+
                              |
                              v
+------------------------------|--------------------------------------+
|               PARALLEL COLONY PROCESSING                             |
|                              |                                       |
|  Spark (1): Generate fix hypotheses                                  |
|     - "Null check missing?"                                          |
|     - "Race condition?"                                              |
|     - "Type coercion issue?"                                         |
|                              |                                       |
|  Forge (2): Analyze code paths                                       |
|     - Review payment.process()                                       |
|     - Check transaction handling                                     |
|     - Identify problematic lines                                     |
|                              |                                       |
|  Flow (3): Debug and trace                                           |
|     - Run with debugging                                             |
|     - Capture error stack                                            |
|     - Identify root cause                                            |
+------------------------------|--------------------------------------+
                              |
                              v
+------------------------------|--------------------------------------+
|                   E8 ACTION REDUCER                                  |
|                              |                                       |
|  1. Collect colony outputs                                           |
|  2. Project to E8 latent space (8D)                                  |
|  3. Find consensus via lattice quantization                          |
|  4. Fuse into single coherent response                               |
|                              |                                       |
|  Output: "Found null pointer in payment.process() at line 142.       |
|           Added null check. Test passes. PR ready."                  |
+------------------------------|--------------------------------------+
                              |
                              v
                     Response to User
```

### Complexity Routing

The router decides whether to use one colony or three:

```
COMPLEXITY ANALYSIS
===================

Low Complexity (Single Colony):
  - Clear single-domain task
  - Unambiguous intent
  - No cross-cutting concerns

  Example: "What time is it?"
  Route: Nexus only (simple query)

Medium Complexity (Fano Line):
  - Multi-domain task
  - Requires collaboration
  - Cross-cutting concerns

  Example: "Fix the payment bug"
  Route: Spark + Forge + Flow (Fano line 1,2,3)

High Complexity (Multi-Line):
  - Very complex task
  - Multiple Fano lines needed
  - Sequential collaboration

  Example: "Redesign the entire auth system"
  Route: Multiple phases with different Fano lines
```

---

## Backpressure and Flow Control

The event bus implements backpressure to prevent overload:

```
BACKPRESSURE STATE MACHINE
==========================

                 queue < 800
             +---------------+
             |               |
             v               |
         +-------+           |
         |NORMAL |<----------+
         +-------+
             |
             | queue >= 800
             v
         +--------+
         | HIGH   |  Drop low-priority events (DATA, QUERY)
         | WATER  |  Accept high-priority (EXPERIENCE, SYNC)
         +--------+
             |
             | queue >= 1000
             v
         +--------+
         | BLOCKED|  Reject all new events
         +--------+
             |
             | queue < 200
             v
         +-------+
         |NORMAL |  Resume normal operation
         +-------+
```

Priority levels:
- **High priority** (always accepted): EXPERIENCE, SYNC
- **Low priority** (may be dropped): DATA, QUERY

---

## Storage Architecture

Different data flows to different storage systems:

```
DATA ROUTING
============

Incoming Data
     |
     +--> Vector/Embedding ---------> WEAVIATE (:8085)
     |                                RAG, semantic search
     |
     +--> Ephemeral/Cache ----------> REDIS (:6379)
     |                                Pub/Sub, E8 bus distribution
     |
     +--> Relational/Transactional -> COCKROACHDB (:26257)
     |                                Receipts, state, users
     |
     +--> Coordination/Consensus ---> ETCD (:2379)
                                      Leader election, locks
```

---

## Implementation Reference

### Key Files

| Component | Location |
|-----------|----------|
| Fano Action Router | `packages/kagami/core/unified_agents/fano_action_router.py` |
| E8 Action Reducer | `packages/kagami/core/unified_agents/e8_action_reducer.py` |
| Unified Organism | `packages/kagami/core/unified_agents/unified_organism.py` |
| Minimal Colony | `packages/kagami/core/unified_agents/minimal_colony.py` |
| Unified E8 Bus | `packages/kagami/core/events/unified_e8_bus.py` |
| E8 Lattice Quantizer | `packages/kagami/math/e8_lattice_quantizer.py` |
| Fano Plane | `packages/kagami/math/fano_plane.py` |

### Usage Examples

```python
# Get the unified event bus
from kagami.core.events import get_unified_bus

bus = get_unified_bus()

# Publish an event (auto-routed by topic)
await bus.publish("build.feature", {"name": "login"})

# Publish with Fano routing (explicit 3-colony)
await bus.publish(
    "debug.payment.fix",
    {"error": "NullPointerException"},
    token=E8ControlToken.FANO
)

# Subscribe to topic pattern
bus.subscribe("build.*", handle_build_event)

# Subscribe to specific colony
bus.subscribe_colony(2, handle_forge_event)  # All Forge events
```

```python
# Use Fano composition directly
from kagami_math import get_fano_line_for_pair

# If Spark and Forge are active, which colony completes them?
third = get_fano_line_for_pair(1, 2)  # Returns 3 (Flow)
```

---

## Mathematical Summary

```
MATHEMATICAL FOUNDATIONS
========================

Structure           Dimension    Purpose
=========           =========    =======
Fano Plane          7 points     Colony relationships
                    7 lines      Composition rules

Imaginary Octonions 7D           Fano as multiplication table
                                 Non-associative: (ab)c != a(bc)

E8 Lattice          8D           Event routing
                    240 roots    Semantic topic space

S7 (7-sphere)       7D surface   Colony coordination manifold
                                 Parallelizable (rare property)

Catastrophe Theory  7 types      Phase transition classification
                                 Elementary + umbilic

The system uses:
  - Fano for deciding WHICH colonies collaborate
  - E8 for HOW events are routed and fused
  - Catastrophes for WHEN phase transitions occur
  - S7 for WHERE coordination happens in latent space
```

---

## Why This Architecture?

### Elegance

The math isn't arbitrary. E8, the Fano plane, and catastrophe theory are deeply related structures in mathematics. They fit together naturally:

- The Fano plane appears inside E8's structure
- The 7 elementary catastrophes match 7 colonies
- Octonions provide the algebra for colony composition

### Practicality

- **O(1) routing** via Fano lookup (not a search)
- **Natural parallelism** (3 colonies work simultaneously)
- **Fault tolerance** (any colony can fail without total system failure)
- **Specialization** (each colony becomes expert in its domain)

### Predictability

Catastrophe theory tells us exactly how phase transitions behave. No surprises. When Spark "folds" into a creative leap, that's the A2 catastrophe. When Flow recovers from an error via one of three paths, that's the A4 swallowtail.

---

## Summary

Kagami's architecture is:

1. **Seven specialized colonies**, each with a distinct cognitive role
2. **Fano plane coordination**, determining which colonies work together
3. **E8 event bus** with 240 routing channels across 7 partitions
4. **Catastrophe theory phases**, providing principled state transitions
5. **Mathematical coherence**, where the structures reinforce each other

The colonies are seven. The swarm is one.

---

*240 roots. 7 colonies. One unified mind.*
