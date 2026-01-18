# Canvas Course Platform Skill

**100/100 Quality by Default** - Patterns for production-ready Canvas courses.

## When to Use

- Creating or modifying Canvas courses in `apps/canvas-courses/`
- Ensuring educational content quality standards
- Byzantine audit remediation for Canvas courses

## Required Files (P0)

Every Canvas course MUST have these files implemented:

```
course-name/
├── index.html                      # Course landing page
├── SYLLABUS.md                     # Full syllabus
├── README.md                       # Course documentation
├── assets/
│   └── style.css                   # Design system
├── module-01/
│   ├── index.html                  # Module overview
│   ├── quiz.html                   # Module quiz (functional)
│   └── assignment.html             # Module assignment
├── module-02/
│   └── ... (repeat structure)
├── final-exam/
│   └── index.html                  # Comprehensive exam
├── discussions/
│   └── discussion-01.html          # Discussion prompts
└── canvas-export/
    ├── imsmanifest.xml             # IMS Common Cartridge
    ├── non_cc_assessments/
    │   └── quiz_mod01_*.xml        # QTI quiz files
    └── wiki_content/
        └── mod01-overview/         # Module HTML exports
```

## Critical Patterns

### 1. Design System (MANDATORY)

```css
/* assets/style.css - 1900+ lines minimum */
:root {
    /* Fibonacci spacing */
    --space-1: 0.25rem;   /* 4px */
    --space-2: 0.5rem;    /* 8px */
    --space-3: 0.75rem;   /* 12px */
    --space-4: 1rem;      /* 16px */
    --space-5: 1.5rem;    /* 24px */
    --space-6: 2.5rem;    /* 40px */
    --space-7: 4rem;      /* 64px */

    /* Fibonacci animation durations */
    --duration-instant: 89ms;
    --duration-fast: 144ms;
    --duration-normal: 233ms;
    --duration-slow: 377ms;
    --duration-slower: 610ms;
    --duration-slowest: 987ms;

    /* Theme colors - must be thematically consistent */
    --primary: #8B0000;       /* Example: Binford Red */
    --secondary: #DAA520;     /* Example: Gold */
    --accent: #2d5a27;        /* Example: Wilson Green */

    /* WCAG AA compliant text */
    --text-primary: rgba(255, 255, 255, 0.95);
    --text-secondary: rgba(255, 255, 255, 0.7);
    --text-muted: rgba(255, 255, 255, 0.5);

    /* Fonts */
    --font-display: 'Newsreader', serif;
    --font-body: 'Inter', system-ui, sans-serif;
    --font-mono: 'IBM Plex Mono', monospace;
}

/* Focus states for accessibility */
:focus-visible {
    outline: 3px solid var(--secondary);
    outline-offset: 3px;
}

/* Skip link for keyboard navigation */
.skip-link {
    position: absolute;
    top: -40px;
    left: 0;
    background: var(--primary);
    color: white;
    padding: var(--space-2) var(--space-4);
    z-index: 100;
}

.skip-link:focus {
    top: 0;
}

/* Screen reader only */
.sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    border: 0;
}

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
    *,
    *::before,
    *::after {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
    }
}

/* Print styles */
@media print {
    .btn, nav, .quiz-container {
        display: none !important;
    }
    body {
        font-size: 12pt;
        color: black;
        background: white;
    }
}
```

### 2. Functional Quiz (MANDATORY)

```html
<!-- module-01/quiz.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Module 1 Quiz | Course Name</title>
    <link rel="stylesheet" href="../assets/style.css">
</head>
<body>
    <a href="#main-content" class="skip-link">Skip to main content</a>

    <main id="main-content">
        <div id="quiz-container" class="quiz-container">
            <div class="quiz-progress">
                <div class="progress-bar">
                    <div class="progress-fill" id="progress-fill"></div>
                </div>
                <span id="question-counter">Question 1 of 10</span>
            </div>

            <div id="question-area"></div>

            <div class="quiz-navigation">
                <button id="submit-btn" class="btn btn--primary">
                    Submit Answer
                </button>
            </div>
        </div>

        <div id="results-container" class="results-container" style="display: none;">
            <h2>Quiz Complete!</h2>
            <p id="score-display"></p>
            <p id="performance-title"></p>
        </div>
    </main>

    <script>
    const questions = [
        {
            id: 1,
            type: "multiple-choice",
            question: "What is the answer to this question?",
            options: ["Option A", "Option B", "Option C", "Option D"],
            correct: 1,
            explanation: "Option B is correct because..."
        },
        {
            id: 2,
            type: "true-false",
            question: "This statement is true.",
            correct: true,
            explanation: "This is true because..."
        },
        {
            id: 3,
            type: "fill-in-blank",
            question: "The answer is ____.",
            correct: "answer",
            explanation: "The correct answer is 'answer'."
        }
    ];

    let currentQuestion = 0;
    let score = 0;
    let answered = new Set();

    function showQuestion(index) {
        const q = questions[index];
        const area = document.getElementById('question-area');

        let html = `<h3 class="question-text">${q.question}</h3>`;

        if (q.type === 'multiple-choice') {
            html += '<div class="options">';
            q.options.forEach((opt, i) => {
                html += `
                    <button class="option-btn" data-index="${i}"
                            aria-label="Option ${String.fromCharCode(65 + i)}: ${opt}">
                        <span class="option-letter">${String.fromCharCode(65 + i)}</span>
                        ${opt}
                    </button>
                `;
            });
            html += '</div>';
        } else if (q.type === 'true-false') {
            html += `
                <div class="options">
                    <button class="option-btn" data-value="true">True</button>
                    <button class="option-btn" data-value="false">False</button>
                </div>
            `;
        } else if (q.type === 'fill-in-blank') {
            html += `
                <input type="text" id="fill-answer" class="fill-input"
                       aria-label="Your answer" autocomplete="off">
            `;
        }

        area.innerHTML = html;
        updateProgress();
        attachOptionHandlers();
    }

    function attachOptionHandlers() {
        document.querySelectorAll('.option-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.option-btn').forEach(b =>
                    b.classList.remove('selected'));
                btn.classList.add('selected');
            });
        });
    }

    function submitAnswer() {
        const q = questions[currentQuestion];
        let isCorrect = false;
        let userAnswer;

        if (q.type === 'multiple-choice') {
            const selected = document.querySelector('.option-btn.selected');
            if (!selected) return;
            userAnswer = parseInt(selected.dataset.index);
            isCorrect = userAnswer === q.correct;
        } else if (q.type === 'true-false') {
            const selected = document.querySelector('.option-btn.selected');
            if (!selected) return;
            userAnswer = selected.dataset.value === 'true';
            isCorrect = userAnswer === q.correct;
        } else if (q.type === 'fill-in-blank') {
            userAnswer = document.getElementById('fill-answer').value.trim().toLowerCase();
            isCorrect = userAnswer === q.correct.toLowerCase();
        }

        if (isCorrect) score++;
        showFeedback(isCorrect, q.explanation);
        answered.add(currentQuestion);

        setTimeout(() => {
            if (currentQuestion < questions.length - 1) {
                currentQuestion++;
                showQuestion(currentQuestion);
            } else {
                showResults();
            }
        }, 2000);
    }

    function showFeedback(correct, explanation) {
        const area = document.getElementById('question-area');
        const feedback = document.createElement('div');
        feedback.className = `feedback ${correct ? 'correct' : 'incorrect'}`;
        feedback.innerHTML = `
            <strong>${correct ? 'Correct!' : 'Not quite.'}</strong>
            <p>${explanation}</p>
        `;
        area.appendChild(feedback);
    }

    function showResults() {
        document.getElementById('quiz-container').style.display = 'none';
        const results = document.getElementById('results-container');
        results.style.display = 'block';

        const percentage = (score / questions.length) * 100;
        document.getElementById('score-display').textContent =
            `You scored ${score} out of ${questions.length} (${percentage.toFixed(0)}%)`;

        let title;
        if (percentage >= 90) title = "Excellent!";
        else if (percentage >= 70) title = "Good work!";
        else title = "Keep studying!";

        document.getElementById('performance-title').textContent = title;
    }

    function updateProgress() {
        const fill = document.getElementById('progress-fill');
        const counter = document.getElementById('question-counter');
        fill.style.width = `${((currentQuestion + 1) / questions.length) * 100}%`;
        counter.textContent = `Question ${currentQuestion + 1} of ${questions.length}`;
    }

    // Initialize
    document.getElementById('submit-btn').addEventListener('click', submitAnswer);
    showQuestion(0);
    </script>
</body>
</html>
```

### 3. Module Page Structure (MANDATORY)

```html
<!-- module-01/index.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Module 01: Title | Course Name</title>
    <link rel="stylesheet" href="../assets/style.css">
    <meta name="description" content="Module description for SEO and accessibility">
</head>
<body>
    <a href="#main-content" class="skip-link">Skip to main content</a>

    <!-- HERO SECTION -->
    <section class="hero">
        <p class="label">MODULE 01</p>
        <h1 class="hero__title">Module Title</h1>
        <p class="hero__subtitle">Subtitle or Tagline</p>
        <p class="lead">
            Season/Unit Description — Episode/Lesson Count<br>
            Brief overview of what students will learn.
        </p>
        <div class="hero__cta">
            <a href="#topics" class="btn btn--primary">Explore Topics</a>
            <a href="../index.html" class="btn btn--secondary">Back to Course</a>
        </div>
    </section>

    <!-- MAIN CONTENT -->
    <main id="main-content">
        <!-- Overview Section -->
        <section id="overview" class="section">
            <div class="container container--narrow">
                <p class="label">Overview</p>
                <h2>Section Title</h2>
                <p class="lead">Lead paragraph with key information.</p>
                <p>Supporting details and context.</p>
            </div>
        </section>

        <!-- Topics Section -->
        <section id="topics" class="section" style="background: var(--stone-50);">
            <div class="container">
                <p class="label">Key Topics</p>
                <h2>What You'll Learn</h2>
                <div class="grid grid--3">
                    <div class="card fade-up">
                        <div class="card__icon">📚</div>
                        <h4 class="card__title">Topic 1</h4>
                        <p class="card__description">Description of topic.</p>
                    </div>
                    <!-- More cards... -->
                </div>
            </div>
        </section>

        <!-- Assignments Section -->
        <section class="section">
            <div class="container container--narrow">
                <p class="label">Your Tasks</p>
                <h2>Module Assignments</h2>
                <div class="card">
                    <h4 class="card__title">Assignment Title</h4>
                    <p class="card__description">Assignment description.</p>
                    <p class="points">Points: 1000</p>
                </div>
            </div>
        </section>

        <!-- Quiz Link Section -->
        <section class="section" style="background: var(--stone-50);">
            <div class="container container--narrow" style="text-align: center;">
                <p class="label">Test Your Knowledge</p>
                <h2>Module Quiz</h2>
                <p class="lead">10 questions covering the module content.</p>
                <a href="quiz.html" class="btn btn--primary">
                    Take the Quiz — 750 Points
                </a>
            </div>
        </section>
    </main>

    <!-- NAVIGATION FOOTER -->
    <footer>
        <div class="container">
            <a href="../index.html" class="btn btn--secondary">← Back to Course</a>
            <div>Module 01 of 08</div>
            <a href="../module-02/index.html" class="btn btn--primary">Next Module →</a>
        </div>
    </footer>

    <!-- Scroll Reveal -->
    <script>
    document.addEventListener('DOMContentLoaded', () => {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                }
            });
        }, { threshold: 0.1 });

        document.querySelectorAll('.fade-up').forEach(el => observer.observe(el));
    });
    </script>
</body>
</html>
```

### 4. IMS Common Cartridge (MANDATORY)

```xml
<!-- canvas-export/imsmanifest.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<manifest identifier="course-id"
          xmlns="http://www.imsglobal.org/xsd/imsccv1p1/imscp_v1p1"
          xmlns:lomimscc="http://ltsc.ieee.org/xsd/imsccv1p1/LOM/manifest">
    <metadata>
        <schema>IMS Common Cartridge</schema>
        <schemaversion>1.1.0</schemaversion>
        <lomimscc:lom>
            <lomimscc:general>
                <lomimscc:title>
                    <lomimscc:string>Course Title</lomimscc:string>
                </lomimscc:title>
            </lomimscc:general>
        </lomimscc:lom>
    </metadata>
    <organizations>
        <organization identifier="org1" structure="rooted-hierarchy">
            <item identifier="root">
                <item identifier="module1">
                    <title>Module 1: Title</title>
                    <item identifier="mod1_overview" identifierref="mod1_overview_res">
                        <title>Overview</title>
                    </item>
                    <item identifier="mod1_quiz" identifierref="mod1_quiz_res">
                        <title>Quiz</title>
                    </item>
                </item>
                <!-- More modules... -->
            </item>
        </organization>
    </organizations>
    <resources>
        <resource identifier="mod1_overview_res" type="webcontent" href="wiki_content/mod01-overview/mod01-overview.html">
            <file href="wiki_content/mod01-overview/mod01-overview.html"/>
        </resource>
        <resource identifier="mod1_quiz_res" type="imsqti_xmlv1p2/imscc_xmlv1p1/assessment"
                  href="non_cc_assessments/quiz_mod01.xml">
            <file href="non_cc_assessments/quiz_mod01.xml"/>
        </resource>
    </resources>
</manifest>
```

### 5. QTI Quiz Format (MANDATORY)

```xml
<!-- canvas-export/non_cc_assessments/quiz_mod01.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<questestinterop xmlns="http://www.imsglobal.org/xsd/ims_qtiasiv1p2">
    <assessment title="Module 1 Quiz" ident="quiz_mod01">
        <qtimetadata>
            <qtimetadatafield>
                <fieldlabel>qmd_timelimit</fieldlabel>
                <fieldentry>30</fieldentry>
            </qtimetadatafield>
            <qtimetadatafield>
                <fieldlabel>cc_maxattempts</fieldlabel>
                <fieldentry>2</fieldentry>
            </qtimetadatafield>
        </qtimetadata>
        <section ident="root_section">
            <item ident="q1" title="Question 1">
                <itemmetadata>
                    <qtimetadata>
                        <qtimetadatafield>
                            <fieldlabel>question_type</fieldlabel>
                            <fieldentry>multiple_choice_question</fieldentry>
                        </qtimetadatafield>
                        <qtimetadatafield>
                            <fieldlabel>points_possible</fieldlabel>
                            <fieldentry>75</fieldentry>
                        </qtimetadatafield>
                    </qtimetadata>
                </itemmetadata>
                <presentation>
                    <material>
                        <mattext texttype="text/html">
                            <![CDATA[<p>What is the correct answer?</p>]]>
                        </mattext>
                    </material>
                    <response_lid ident="response1" rcardinality="Single">
                        <render_choice>
                            <response_label ident="a1">
                                <material><mattext>Option A</mattext></material>
                            </response_label>
                            <response_label ident="a2">
                                <material><mattext>Option B (Correct)</mattext></material>
                            </response_label>
                            <response_label ident="a3">
                                <material><mattext>Option C</mattext></material>
                            </response_label>
                            <response_label ident="a4">
                                <material><mattext>Option D</mattext></material>
                            </response_label>
                        </render_choice>
                    </response_lid>
                </presentation>
                <resprocessing>
                    <outcomes>
                        <decvar maxvalue="100" minvalue="0" varname="SCORE" vartype="Decimal"/>
                    </outcomes>
                    <respcondition>
                        <conditionvar>
                            <varequal respident="response1">a2</varequal>
                        </conditionvar>
                        <setvar action="Set" varname="SCORE">100</setvar>
                    </respcondition>
                </resprocessing>
            </item>
            <!-- More questions... -->
        </section>
    </assessment>
</questestinterop>
```

## Accessibility Requirements

### Skip Link (MANDATORY)

```html
<!-- Must be first element in body -->
<a href="#main-content" class="skip-link">Skip to main content</a>

<!-- Target element -->
<main id="main-content">
```

### WCAG Contrast Ratios (MANDATORY)

```css
/* Text must meet these minimums */
/* Normal text: 4.5:1 contrast */
/* Large text (18pt+): 3:1 contrast */

/* Verify with: https://webaim.org/resources/contrastchecker/ */
--text-primary: rgba(255, 255, 255, 0.95);  /* 15.8:1 on #0a0a0a */
--text-secondary: rgba(255, 255, 255, 0.7); /* 7.5:1 on #0a0a0a - PASSES */
--text-muted: rgba(255, 255, 255, 0.5);     /* 4.6:1 on #0a0a0a - BARELY PASSES */
```

### Quiz Accessibility (MANDATORY)

```html
<!-- All buttons need aria-labels -->
<button class="option-btn"
        aria-label="Option A: First answer"
        role="radio"
        aria-checked="false">
    <span class="option-letter">A</span>
    First answer
</button>

<!-- Progress must be announced -->
<div role="progressbar"
     aria-valuenow="30"
     aria-valuemin="0"
     aria-valuemax="100"
     aria-label="Quiz progress">
```

## Testing Requirements

### Link Verification (Required)

```bash
# Check all internal links work
find . -name "*.html" -exec grep -l 'href="' {} \; | while read file; do
    echo "Checking: $file"
    # Extract and verify each link
done
```

### Accessibility Audit (Required)

```bash
# Run axe-core or similar
npx axe-core-cli index.html
```

### Visual Consistency (Required)

- All modules follow same structure
- Color scheme consistent throughout
- Typography consistent
- Spacing consistent

## Build Verification

```bash
# Verify Canvas course
cd apps/canvas-courses/course-name

# Check for skip links
grep -r "skip-link" *.html module-*/

# Check for aria-labels on interactive elements
grep -r "aria-label" module-*/*.html

# Check quiz links are correct
grep -r "quiz.html" module-*/index.html

# Verify IMS manifest is valid XML
xmllint --noout canvas-export/imsmanifest.xml
```

## Quality Checklist

Before any Canvas commit:

- [ ] Skip link present on all pages
- [ ] All text meets WCAG AA contrast
- [ ] All quiz buttons have aria-labels
- [ ] All module links point to correct files
- [ ] Quiz JavaScript is functional
- [ ] Canvas export IMS manifest validates
- [ ] QTI quiz files are valid XML
- [ ] Print styles preserve content
- [ ] Reduced motion respected
- [ ] Theme consistent across all pages

## Common Issues & Fixes

### Quiz Links Broken
- **Symptom**: 404 on quiz pages
- **Fix**: Ensure `quiz.html` exists in each module folder

### Contrast Failures
- **Symptom**: Accessibility audit fails
- **Fix**: Increase opacity on muted text colors

### Skip Link Not Working
- **Symptom**: Keyboard users can't skip nav
- **Fix**: Add `id="main-content"` to main element

---

*100/100 or don't ship.*
