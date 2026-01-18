# Canvas Import Guide for Tool Time University

## Course Code: TVST-1991

This guide explains how to import Tool Time University into Canvas LMS, configure the Home Equity grading system, and set up badges/achievements.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Importing the Course Package](#importing-the-course-package)
3. [Setting Up the Home Equity Grading Scheme](#setting-up-the-home-equity-grading-scheme)
4. [Configuring Assignment Groups](#configuring-assignment-groups)
5. [Setting Up Badges and Achievements](#setting-up-badges-and-achievements)
6. [Post-Import Configuration](#post-import-configuration)
7. [Troubleshooting Common Issues](#troubleshooting-common-issues)

---

## Prerequisites

Before importing, ensure you have:

- **Canvas Administrator or Instructor access** to the target course shell
- **Import privileges** enabled for your account
- The **canvas-export** folder from this package (contains imsmanifest.xml and all resources)
- A **blank course shell** created in Canvas

### Supported Canvas Versions

This package follows IMS Common Cartridge 1.1 specification and is compatible with:
- Canvas LMS (Instructure)
- Open-source Canvas installations
- Canvas Free for Teachers accounts

---

## Importing the Course Package

### Step 1: Prepare the Export Package

1. Navigate to the `canvas-export` folder in this repository
2. Create a ZIP file containing all contents:
   ```
   canvas-export/
   ├── imsmanifest.xml
   ├── course_settings/
   │   ├── course_settings.xml
   │   └── assignment_groups.xml
   ├── outcomes.xml
   ├── module-01/
   ├── module-02/
   ... (all module folders)
   ```

3. Name the ZIP file: `tool-time-university-canvas-export.zip`

### Step 2: Import via Canvas

1. **Navigate to your course** in Canvas
2. Go to **Settings** (left sidebar)
3. Click **Import Course Content** (right sidebar)
4. Select **Content Type**: `Common Cartridge 1.x Package`
5. Click **Choose File** and select your ZIP
6. Under **Content**, select `All content`
7. Click **Import**

### Step 3: Monitor Import Progress

- Watch the **Current Jobs** section for progress
- Import typically completes in 2-5 minutes
- Check for any warning messages (usually non-critical)

---

## Setting Up the Home Equity Grading Scheme

The Home Equity Points system replaces traditional percentages with dollar amounts inspired by the Home Improvement board game.

### Creating the Custom Grading Scheme

1. Go to **Settings** > **Course Details**
2. Scroll to **Grading Scheme**
3. Click **view grading scheme** then **Manage Grading Schemes**
4. Click **+ Add Grading Scheme**
5. Name it: `Home Equity Points`
6. Enter the following thresholds:

| Grade Name | Minimum % | Home Equity Equivalent |
|------------|-----------|------------------------|
| Master Craftsman (A) | 90% | $55,800+ |
| Journeyman Builder (B) | 80% | $49,600+ |
| Apprentice (C) | 70% | $43,400+ |
| Weekend Warrior (D) | 60% | $37,200+ |
| Tim After a Disaster (F) | 0% | Below $37,200 |

7. Click **Save**
8. Return to Course Details and select this scheme
9. Check **Enable course grading scheme**
10. Click **Update Course Details**

### Point Value Reference

Total Course Points: **$62,000 Home Equity Dollars**

| Assignment Type | Per Item | Count | Total |
|-----------------|----------|-------|-------|
| Tool Time Challenges | $2,500 | 8 | $20,000 |
| Binford Project Cards | $1,500 | 8 | $12,000 |
| Wilson's Reflections | $2,000 | 4 | $8,000 |
| Quizzes | $750 | 8 | $6,000 |
| Discussions | $500 | 8 | $4,000 |
| Participation | varies | - | $2,000 |
| Final Project | $10,000 | 1 | $10,000 |

---

## Configuring Assignment Groups

The assignment groups should import automatically. Verify the weights match:

| Group | Weight | Purpose |
|-------|--------|---------|
| Tool Time Challenges | 32% | Major creative analyses |
| Binford Project Cards | 19% | Hands-on documentation |
| Wilson's Reflections | 13% | Philosophical essays |
| Participation | 6% | Engagement activities |
| Final Project | 16% | Episode writing project |
| Quizzes | 10% | Module trivia challenges |
| Discussions | 4% | Forum participation |

### Manual Configuration (if needed)

1. Go to **Assignments**
2. Click the **gear icon** > **Assignment Groups Weight**
3. Check **Weight final grade based on assignment groups**
4. Enter weights as shown above
5. Click **Save**

---

## Setting Up Badges and Achievements

Canvas supports badges through **Canvas Badges** (Badgr integration) or **custom solutions**.

### Option A: Canvas Badges (Badgr)

If your institution has Badgr enabled:

1. Go to **Admin** > **Badgr** (or ask your admin)
2. Create a new badge collection: **Tool Time University**
3. Create the following badges:

#### Achievement Badges

| Badge | Criteria | Image Theme |
|-------|----------|-------------|
| **Pilot Light** | Complete Module 1 | Pilot flame icon |
| **Assembly Required** | Complete Module 2 | Tools/parts icon |
| **Measure Twice** | Complete Module 3 | Measuring tape |
| **Load-Bearing** | Complete Module 4 | House frame |
| **Rewired** | Complete Module 5 | Electrical plug |
| **Heavy Machinery** | Complete Module 6 | Power tool |
| **The Addition** | Complete Module 7 | House extension |
| **Final Inspection** | Complete Module 8 | Clipboard check |

#### Mastery Badges

| Badge | Criteria | Image Theme |
|-------|----------|-------------|
| **First Grunt** | First assignment submitted | Speech bubble "AEUHHH" |
| **Flannel Approved** | Score 90%+ on any quiz | Al's flannel pattern |
| **Fence Philosopher** | Complete all Wilson Reflections | Fence silhouette |
| **Binford Certified** | Complete all Project Cards | Binford logo |
| **Master Craftsman** | Earn $55,800+ total | Master badge/trophy |
| **Tool Time MVP** | Complete Final Project | Tool Time logo |

### Option B: Manual Badge System

If Badgr isn't available, create a manual tracking system:

1. Create a **Page** titled "Your Achievements"
2. Use the HTML from `leaderboard.html` as a template
3. Update student progress manually or through announcements

### Option C: Third-Party Integration

Consider these Canvas-compatible badge platforms:
- **Credly** (digital credentials)
- **Open Badges** (Mozilla specification)
- **Acclaim** (professional certifications)

---

## Post-Import Configuration

### 1. Review Module Structure

1. Go to **Modules**
2. Verify all 8 modules plus Final Project imported
3. Check that items are in correct order within each module
4. Publish modules as appropriate for your schedule

### 2. Set Due Dates

Due dates are not included in the package. Set them based on your schedule:

1. Go to **Assignments**
2. Click each assignment > **Edit**
3. Set **Due Date** and **Available from/until** dates
4. Recommended pace: 1 module per week

### 3. Configure Quizzes

Quizzes import as reference content. To make them functional:

1. Go to **Quizzes**
2. Click **+ Quiz** for each module
3. Use the HTML quiz files as reference for questions
4. Set quiz options:
   - **Attempts**: 2 allowed
   - **Time limit**: None (open book)
   - **Show correct answers**: After submission

### 4. Customize Announcements

Rename the Announcements link to match the course theme:

1. **Settings** > **Navigation**
2. Drag **Announcements** to hidden
3. Use **Pages** to create a "Tool Time Bulletins" page instead

### 5. Update Syllabus

1. Go to **Syllabus**
2. Add your institution's required language
3. Include office hours and contact information
4. Reference the Home Equity grading scheme

---

## Troubleshooting Common Issues

### Import Fails or Hangs

**Symptoms**: Import stuck at percentage, error message

**Solutions**:
1. Check ZIP file isn't corrupted (re-create from source)
2. Ensure imsmanifest.xml is at root level of ZIP
3. Try importing with "Overwrite" disabled
4. Contact Canvas support if persistent

### Missing Content After Import

**Symptoms**: Modules present but items missing

**Solutions**:
1. Check **Files** area for orphaned content
2. Manually link files to modules if needed
3. Re-import specific missing resources

### Grading Scheme Not Applied

**Symptoms**: Grades show percentages, not Home Equity

**Solutions**:
1. Verify scheme was created correctly
2. Ensure scheme is selected in Course Details
3. Check that "Enable course grading scheme" is checked
4. Refresh the page/clear cache

### Assignment Groups Wrong Weight

**Symptoms**: Final grades don't match expected calculation

**Solutions**:
1. Go to **Assignments** > gear > **Assignment Groups Weight**
2. Verify percentages total exactly 100%
3. Ensure each assignment is in correct group
4. Check that "Weight final grade" is enabled

### Outcomes Not Aligned

**Symptoms**: Outcomes exist but aren't linked to assignments

**Solutions**:
1. Go to **Outcomes**
2. Verify outcome groups imported
3. For each assignment, click **Edit** > **Rubric** > add outcomes
4. Manually align if auto-alignment failed

### HTML Formatting Issues

**Symptoms**: Pages display raw HTML or broken styling

**Solutions**:
1. Edit the page in Canvas
2. Switch to **HTML Editor**
3. Clean up any unsupported tags
4. Canvas strips certain JavaScript - this is expected

### Quiz Questions Not Importing

**Symptoms**: Quiz pages show but no questions

**Solutions**:
Quiz content in this package is reference HTML, not QTI format.
1. Create quizzes manually in Canvas
2. Use the HTML files as question banks
3. Copy/paste questions into Canvas quiz editor

---

## File Structure Reference

```
canvas-export/
├── imsmanifest.xml              # Course manifest (required)
├── outcomes.xml                  # Learning outcomes
├── course_settings/
│   ├── course_settings.xml      # Course metadata
│   └── assignment_groups.xml    # Assignment group weights
├── module-01/                   # Season 1 content
│   ├── 01-module-overview.html
│   ├── 02-lesson-pilot-episode.html
│   ├── 03-assignment-binford-project-card.html
│   ├── 04-quiz-season1-trivia.html
│   └── 05-discussion-wilsons-wisdom.html
├── module-02/ through module-08/
├── final-exam/                  # Final project content
└── assets/
    └── style.css                # Shared stylesheet
```

---

## Support Resources

### Canvas Documentation
- [Importing Content](https://community.canvaslms.com/docs/DOC-12656)
- [Grading Schemes](https://community.canvaslms.com/docs/DOC-26521)
- [Learning Outcomes](https://community.canvaslms.com/docs/DOC-12904)

### Tool Time University
- Course README: `../README.md`
- Sample content: `../module-01/`
- Leaderboard template: `../leaderboard.html`

---

## Credits

Tool Time University is a fan-created educational parody.

*Home Improvement* is the property of Disney/ABC and Wind Dancer Productions.

Course structure follows Canvas LMS and IMS Common Cartridge specifications.

---

*"Does everybody know what time it is?"*

**TOOL TIME!**

*Happy teaching!*
