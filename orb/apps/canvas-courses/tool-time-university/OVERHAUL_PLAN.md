# Tool Time University: Comprehensive Overhaul Plan

## Executive Summary

Transform TTU from a static HTML course into a **fully interactive, gamified Canvas-native learning experience** that rivals Duolingo's engagement mechanics while maintaining deep fan authenticity.

**Current State:** 88/100 (Journeyman Builder)
**Target State:** 110/100 (Master Craftsman+)

---

## Phase 1: Foundation Fixes (CRITICAL)

### 1.1 Convert All HTML Quizzes to Native Canvas QTI

**Problem:** Modules 2-8 have HTML-based quizzes that don't integrate with Canvas gradebook.

**Solution:** Convert all 8 quiz files to QTI 1.2 XML format with:
- Proper `answer_weight` attributes (not just condition titles)
- Canvas-compatible question types
- Automatic grading integration

**Files to Convert:**
- `module-02/quiz.html` → `quiz_mod02_season2.xml`
- `module-03/quiz.html` → `quiz_mod03_season3.xml`
- `module-04/quiz.html` → `quiz_mod04_season4.xml`
- `module-05/quiz.html` → `quiz_mod05_season5.xml`
- `module-06/quiz.html` → `quiz_mod06_season6.xml`
- `module-07/quiz.html` → `quiz_mod07_season7.xml`
- `module-08/quiz.html` → `quiz_mod08_season8.xml`
- `final-exam/index.html` → `quiz_final_exam.xml`

### 1.2 Fix Module Prerequisites

**Current:** All modules unlocked simultaneously
**Target:** Sequential progression with mastery requirements

```
Module 1 → (75% quiz score) → Module 2 → ... → Module 8 → Final Exam
```

### 1.3 Create Assignment Groups with Weights

| Group | Weight | Items |
|-------|--------|-------|
| Tool Time Challenges | 30% | 8 creative projects |
| Binford Project Cards | 25% | 8 hands-on assignments |
| Season Quizzes | 20% | 8 trivia quizzes |
| Wilson's Reflections | 15% | 4 philosophical essays |
| Final Project | 10% | Episode script |

---

## Phase 2: Gamification Enhancement

### 2.1 Duolingo-Style Mechanics

#### Streak System
- Track consecutive days of engagement
- "Tool Time Streak" badge tiers: 7, 30, 100 days
- Streak freeze available (costs Home Equity)

#### XP/Home Equity Leaderboard
- Weekly leaderboards by Home Equity earned
- Leagues: Weekend Warrior → Apprentice → Journeyman → Master Craftsman
- Promotion/demotion based on weekly performance

#### Achievement Badges (Canvas Credentials)

| Badge | Requirement | Icon |
|-------|-------------|------|
| Pilot Light | Complete Module 1 | 🔥 |
| Flannel Master | Score 100% on Al-related questions | 👔 |
| Grunt Guru | Complete Grunt Taxonomy assignment | 🦍 |
| Wilson's Apprentice | 4 Wilson Reflections submitted | 🌿 |
| More Power! | Complete all Tool Time Challenges | ⚡ |
| Master Craftsman | Earn $50,000 Home Equity | 🏆 |
| Perfect Season | 100% on any season quiz | ⭐ |
| Binford Certified | Complete Final Project | 🔧 |

### 2.2 Progress Visualization

- Home Equity progress bar on course homepage
- Module completion percentages
- "Next milestone" indicators
- Seasonal progress tracking

---

## Phase 3: Mastery Paths

### 3.1 Adaptive Learning Paths

After each quiz, branch based on score:

```
Quiz Score ≥ 90%: "Expert Path"
  → Bonus deep-dive content
  → Advanced discussion prompts
  → Extra credit opportunities

Quiz Score 70-89%: "Standard Path"
  → Normal module progression
  → Standard assignments

Quiz Score < 70%: "Remediation Path"
  → Review materials
  → Practice quiz
  → Re-attempt original quiz
```

### 3.2 Personalized Content

- **Tim Track:** Focus on Tool Time disasters, technical failures
- **Jill Track:** Focus on family dynamics, character development
- **Wilson Track:** Focus on philosophy, cultural references
- **Al Track:** Focus on craftsmanship, safety, competence

---

## Phase 4: Learning Outcomes & Rubrics

### 4.1 Course Learning Outcomes

1. **Television History (TVST-101)**
   - Analyze 90s sitcom conventions and their cultural impact
   - Mastery: 80% on historical context questions

2. **Character Analysis (TVST-102)**
   - Evaluate character development across 8 seasons
   - Mastery: Complete 4 character-focused assignments

3. **Cultural Studies (TVST-103)**
   - Connect Home Improvement themes to broader cultural trends
   - Mastery: Wilson's Reflections essays

4. **Creative Writing (TVST-104)**
   - Demonstrate ability to write in show's voice/format
   - Mastery: Final Project episode script

### 4.2 Rubric Templates

**Tool Time Challenge Rubric:**
| Criterion | Excellent (4) | Good (3) | Satisfactory (2) | Needs Work (1) |
|-----------|---------------|----------|------------------|----------------|
| Fan Authenticity | Deep show knowledge evident | Good references | Basic understanding | Factual errors |
| Analysis Depth | Insightful, original observations | Solid analysis | Surface-level | Missing analysis |
| Creativity | Exceptional originality | Creative approach | Standard execution | Lacks creativity |
| Presentation | Professional quality | Well-organized | Adequate | Disorganized |

---

## Phase 5: Interactive Content

### 5.1 H5P Integration Opportunities

- **Interactive Videos:** Embed questions in episode clips
- **Branching Scenarios:** "What Would Tim Do?" decision trees
- **Timeline:** Interactive show history
- **Drag & Drop:** Match characters to quotes
- **Image Hotspots:** Tool Time set exploration

### 5.2 Discussion Enhancements

- Threaded discussions with peer review requirements
- "Wilson's Wisdom" weekly prompts
- Debate topics (Tim vs Al approaches)
- Fan theory discussions

---

## Phase 6: Technical Implementation

### 6.1 Canvas API Automation

```python
# Programmatic course enhancement
async def enhance_course():
    # 1. Create all QTI quizzes
    for module in range(2, 9):
        quiz_id = await create_quiz(module)
        await add_questions(quiz_id, module)
        await publish_quiz(quiz_id)

    # 2. Set module prerequisites
    for i, module in enumerate(modules[1:], 1):
        await set_prerequisite(module, modules[i-1])

    # 3. Create outcomes
    outcomes = await create_outcomes(LEARNING_OUTCOMES)

    # 4. Create rubrics linked to outcomes
    rubrics = await create_rubrics(outcomes)

    # 5. Update assignments with rubrics
    for assignment in assignments:
        await link_rubric(assignment, rubrics)
```

### 6.2 File Structure After Overhaul

```
canvas-export/
├── imsmanifest.xml (updated with all new resources)
├── non_cc_assessments/
│   ├── quiz_mod01_season1.xml ✓
│   ├── quiz_mod02_season2.xml (NEW)
│   ├── quiz_mod03_season3.xml (NEW)
│   ├── quiz_mod04_season4.xml (NEW)
│   ├── quiz_mod05_season5.xml (NEW)
│   ├── quiz_mod06_season6.xml (NEW)
│   ├── quiz_mod07_season7.xml (NEW)
│   ├── quiz_mod08_season8.xml (NEW)
│   └── quiz_final_exam.xml (NEW)
├── outcomes.xml (enhanced)
├── course_settings/
│   ├── assignment_groups.xml (weighted)
│   └── rubrics/
│       └── rubrics.xml (expanded)
└── module-*/
    └── (existing content)
```

---

## Implementation Priority

### Immediate (This Session)
1. ✅ Fix Season 1 quiz answers via API
2. ✅ Fix broken wiki page links
3. 🔄 Convert Modules 2-8 quizzes to QTI
4. 🔄 Set module prerequisites
5. 🔄 Create assignment groups with weights

### Short-term
6. Create learning outcomes
7. Build rubrics
8. Link rubrics to assignments
9. Configure Mastery Paths

### Future Enhancement
10. Digital badges (requires Canvas Credentials)
11. H5P interactive content
12. Leaderboard implementation
13. Streak tracking system

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Native Canvas Quizzes | 1/9 | 9/9 |
| Module Prerequisites | 0% | 100% |
| Graded Assignments | ~50% | 100% |
| Learning Outcomes | 0 | 4+ |
| Rubrics | 0 | 4+ |
| Achievement Badges | 0 | 8+ |
| Fan Authenticity Score | 90% | 100% |

---

## The Vision

**Tool Time University becomes the gold standard for fan-created educational content** - a course so engaging that students:
- Return daily (streak mechanics)
- Compete for rankings (leaderboards)
- Earn shareable credentials (badges)
- Experience personalized learning (Mastery Paths)
- Actually learn television history while having fun

*"If it doesn't say Binford, someone else made it."*
*If it doesn't feel like Tool Time, we haven't made it right.*

---

**ARUH ARUH ARUH! MORE POWER TO THE COURSE!**
