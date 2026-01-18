# Canvas LMS Skill

Educational platform integration via Canvas MCP Server (54 tools).

## Domain

Digital - Learning Management

## Dependencies

- Requires: API (network)
- Enhances: Composio (calendar sync, notifications)
- Feeds: World Model (educational state)

## Signals

- Trigger words: canvas, course, assignment, grade, quiz, module, syllabus, submission, enrollment, discussion, announcement
- Context: Educational tasks, course management, grading workflows

## Tools (MCP)

Canvas MCP Server provides 54 tools. Call them via MCP tool interface.

### Student Tools (33)

| Tool | Purpose |
|------|---------|
| `canvas_health_check` | Verify API connectivity |
| `canvas_list_courses` | List enrolled courses |
| `canvas_get_course` | Get course details |
| `canvas_list_assignments` | List assignments for a course |
| `canvas_get_assignment` | Get assignment details |
| `canvas_submit_assignment` | Submit work to assignment |
| `canvas_get_submission` | Get submission status |
| `canvas_list_modules` | List course modules |
| `canvas_get_module` | Get module details |
| `canvas_list_module_items` | List items in module |
| `canvas_mark_module_item_complete` | Mark module item done |
| `canvas_list_discussion_topics` | List discussions |
| `canvas_get_discussion_topic` | Get discussion details |
| `canvas_post_to_discussion` | Post to discussion |
| `canvas_list_announcements` | List course announcements |
| `canvas_get_user_grades` | Get user's grades |
| `canvas_get_course_grades` | Get course grades |
| `canvas_get_dashboard` | Get dashboard overview |
| `canvas_get_dashboard_cards` | Get dashboard course cards |
| `canvas_get_upcoming_assignments` | Get upcoming due dates |
| `canvas_list_calendar_events` | List calendar events |
| `canvas_list_files` | List course files |
| `canvas_get_file` | Download file |
| `canvas_list_folders` | List file folders |
| `canvas_list_pages` | List course pages |
| `canvas_get_page` | Get page content |
| `canvas_list_conversations` | List messages |
| `canvas_get_conversation` | Get conversation |
| `canvas_create_conversation` | Send message |
| `canvas_list_notifications` | List notifications |
| `canvas_get_syllabus` | Get course syllabus |
| `canvas_get_user_profile` | Get user profile |
| `canvas_update_user_profile` | Update profile |

### Instructor Tools (13)

| Tool | Purpose |
|------|---------|
| `canvas_create_course` | Create course (requires account_id) |
| `canvas_update_course` | Update course settings |
| `canvas_create_assignment` | Create new assignment |
| `canvas_update_assignment` | Update assignment |
| `canvas_list_assignment_groups` | List assignment groups |
| `canvas_submit_grade` | Grade a submission |
| `canvas_enroll_user` | Enroll user in course |
| `canvas_list_quizzes` | List course quizzes |
| `canvas_get_quiz` | Get quiz details |
| `canvas_create_quiz` | Create new quiz |
| `canvas_start_quiz_attempt` | Start quiz attempt |
| `canvas_list_rubrics` | List grading rubrics |
| `canvas_get_rubric` | Get rubric details |

### Admin Tools (7)

| Tool | Purpose |
|------|---------|
| `canvas_get_account` | Get account info |
| `canvas_list_account_courses` | List all courses in account |
| `canvas_list_account_users` | List all users in account |
| `canvas_create_user` | Create new user |
| `canvas_list_sub_accounts` | List sub-accounts |
| `canvas_get_account_reports` | Get account reports |
| `canvas_create_account_report` | Generate report |

## Configuration

API token stored in:
- Keychain: `security find-generic-password -s "kagami" -a "canvas_api_token" -w`
- MCP Config: `.mcp.json` → `canvas` server

Domain: `canvas.instructure.com`

## Usage Examples

### Check Upcoming Assignments

```
User: "What assignments are due this week?"

Kagami:
1. canvas_list_courses → get course IDs
2. canvas_get_upcoming_assignments → get due dates
3. Format response with deadlines
```

### Get Course Grades

```
User: "How am I doing in my courses?"

Kagami:
1. canvas_list_courses → enumerate courses
2. canvas_get_course_grades → for each course
3. Summarize grade status
```

### Submit Assignment

```
User: "Submit my essay to English 101"

Kagami:
1. canvas_list_courses → find English 101
2. canvas_list_assignments → find target assignment
3. canvas_submit_assignment → submit work
4. canvas_get_submission → confirm submission
```

### Grade Student Work

```
User: "Grade the submissions for Assignment 3"

Kagami:
1. canvas_list_courses → find course
2. canvas_get_assignment → get assignment details
3. canvas_list_rubrics → get grading rubric
4. For each submission:
   - Review work
   - canvas_submit_grade → assign grade with feedback
```

### Create New Assignment

```
User: "Create a homework assignment due Friday"

Kagami:
1. canvas_list_courses → select course
2. canvas_create_assignment → create with:
   - name, description
   - due_at: Friday datetime
   - points_possible
   - submission_types
```

## Automation Opportunities

### Daily Briefing

```python
# Morning educational briefing
async def educational_briefing():
    courses = await canvas_list_courses()
    upcoming = await canvas_get_upcoming_assignments()
    announcements = await canvas_list_announcements()

    return f"""
    ## Today's Canvas Summary

    ### Due Soon
    {format_assignments(upcoming)}

    ### New Announcements
    {format_announcements(announcements)}
    """
```

### Grade Reminders

```python
# Remind about ungraded submissions
async def check_ungraded():
    for course in instructor_courses:
        assignments = await canvas_list_assignments(course_id)
        for assignment in assignments:
            submission = await canvas_get_submission(course_id, assignment_id)
            if submission.workflow_state == 'submitted':
                # Alert instructor
                pass
```

### Discussion Participation

```python
# Track discussion engagement
async def discussion_status(course_id):
    discussions = await canvas_list_discussion_topics(course_id)
    participation = []
    for disc in discussions:
        topic = await canvas_get_discussion_topic(course_id, disc.id)
        participation.append({
            'topic': topic.title,
            'posts_required': topic.posts_required,
            'my_posts': count_my_posts(topic)
        })
    return participation
```

## Safety Constraints

h(x) >= 0 for all Canvas operations:

- **Privacy**: Only access own data unless instructor role
- **Academic Integrity**: Never auto-complete quizzes or assignments
- **Grade Accuracy**: Double-confirm before submitting grades
- **Communication**: Draft messages for review before sending

## Cross-Domain Integration

### With Composio

```python
# Sync Canvas events to Google Calendar
async def sync_canvas_calendar():
    events = await canvas_list_calendar_events()
    for event in events:
        await composio.execute_action(
            "GOOGLECALENDAR_CREATE_EVENT",
            {
                "summary": event.title,
                "start": event.start_at,
                "end": event.end_at,
                "description": f"Canvas: {event.context_name}"
            }
        )
```

### With Smart Home

```python
# Study mode activation
async def study_mode(course_name):
    # Set environment
    await smart_home.set_lights(70, rooms=["Office"])
    await smart_home.spotify_play_playlist("focus")

    # Load course materials
    course = await find_course(course_name)
    materials = await canvas_list_pages(course.id)

    return f"Study mode activated for {course_name}"
```

## Key Files

| File | Purpose |
|------|---------|
| `.mcp.json` | MCP server configuration |
| `packages/kagami/core/services/canvas/` | Canvas service (future) |

## Troubleshooting

### "401 Unauthorized"

Token expired or invalid. Regenerate at:
Canvas → Account → Settings → Approved Integrations → New Access Token

### "Page not found" on course creation

Course creation requires `account_id`. Get it first:
```
canvas_get_account → use returned ID
canvas_create_course(account_id=...)
```

### Rate Limits

Canvas API has rate limits. Space out bulk operations.

---

*Canvas integration enables Kagami to be a complete educational assistant.*
