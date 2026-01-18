# App Store Privacy Labels - Kagami Watch

This document specifies the privacy labels required for App Store submission.
Per audit: Document App Privacy labels required for App Store compliance.

## Data Types Collected

### 1. Health & Fitness Data

**Type:** Health
**Purpose:** App Functionality, Analytics
**Linked to User:** Yes
**Tracking:** No

**Details:**
- Heart rate data (read-only from HealthKit)
- Sleep analysis data (read-only from HealthKit)
- Activity/workout data (read-only from HealthKit)

**Usage:**
- Context-aware home automation suggestions
- Sleep detection for Goodnight scene activation
- Workout detection for relevant Smart Stack display

### 2. Identifiers

**Type:** User ID
**Purpose:** App Functionality
**Linked to User:** Yes
**Tracking:** No

**Details:**
- Internal user identifier for multi-user household support
- Authentication token for Kagami server communication

**Usage:**
- Associating user preferences with correct household member
- Secure communication with Kagami home server

### 3. Usage Data

**Type:** Product Interaction
**Purpose:** App Functionality, Analytics
**Linked to User:** No
**Tracking:** No

**Details:**
- Scene activation events
- Voice command transcripts (processed locally, not stored)
- Feature usage frequency

**Usage:**
- Improving context-aware suggestions
- Optimizing frequently-used scenes

### 4. Location Data

**Type:** Coarse Location
**Purpose:** App Functionality
**Linked to User:** No
**Tracking:** No

**Details:**
- Home/away status (derived, not precise location)
- WiFi network presence detection

**Usage:**
- Welcome Home scene automation
- Away mode activation

### 5. Diagnostics

**Type:** Crash Data, Performance Data
**Purpose:** App Functionality
**Linked to User:** No
**Tracking:** No

**Details:**
- Crash reports
- Connection reliability metrics
- Response time data

**Usage:**
- App stability improvements
- Performance optimization

---

## Age Rating Questionnaire Notes

Per audit: Note age rating questionnaire requirement.

### Recommended Rating: 4+

**Questionnaire Responses:**

1. **Cartoon or Fantasy Violence:** None
2. **Realistic Violence:** None
3. **Sexual Content or Nudity:** None
4. **Profanity or Crude Humor:** None
5. **Alcohol, Tobacco, or Drug Use:** None
6. **Mature/Suggestive Themes:** None
7. **Simulated Gambling:** None
8. **Horror/Fear Themes:** None
9. **Medical/Treatment Information:** None (HealthKit is for automation only)
10. **Unrestricted Web Access:** None (communicates only with home server)

### Special Considerations

- App requires iOS 17.0+ / watchOS 10.0+
- App requires active home network connection
- App accesses HealthKit with explicit user permission
- App controls physical home devices (lights, locks, etc.)

---

## HealthKit Data Handling

Per audit: Verify HealthKit data handling per App Store rules.

### Data Collection

1. **Types Read:**
   - `HKQuantityType.heartRate`
   - `HKCategoryType.sleepAnalysis`
   - `HKQuantityType.activeEnergyBurned`
   - `HKWorkoutType.workoutType()`

2. **Types Written:** None

### Data Storage

- HealthKit data is **not stored** on device beyond current session
- HealthKit data is **not transmitted** to external servers
- HealthKit data is used **only** for local context inference

### Data Processing

- Heart rate: Used to detect workout state (high HR = workout)
- Sleep analysis: Used to detect sleep state for Goodnight automation
- Activity: Used for Smart Stack relevance calculation

### User Consent

- Authorization requested on first launch via HealthKit authorization flow
- User can revoke access in Settings > Privacy > Health > Kagami
- App functions with reduced features if HealthKit access denied

---

## Data Deletion Compliance

Per audit: Add data deletion compliance documentation.

### User Data Deletion

Users can request deletion of their data through:

1. **In-App:** Settings > Account > Delete My Data
2. **Email:** privacy@kagami.local (household admin)
3. **Automatic:** Removing the app deletes all local data

### Data Retained

Upon deletion request, the following is removed:
- User authentication tokens
- Cached home state
- Scene preferences
- Analytics data associated with user ID

### Data Not Stored

The following is never stored and requires no deletion:
- HealthKit data (read-only, not persisted)
- Voice command audio (processed locally, not stored)
- Location data (derived status only)

### Timeline

- Local data: Deleted immediately upon request
- Server data: Deleted within 30 days per Kagami privacy policy

---

## Third-Party Data Sharing

Kagami Watch does **not** share data with third parties.

All data communication is:
- Between Watch and iPhone (via WatchConnectivity)
- Between Watch and local Kagami server (on home network)

No data is transmitted to:
- Cloud services
- Analytics providers
- Advertising networks
- Any external servers

---

## Privacy Policy URL

https://kagami.local/privacy

(Replace with actual public URL for App Store submission)

---

## Attestation

This privacy documentation accurately represents the data practices
of Kagami Watch as of 2025-12-30.

Reviewed by: Kagami Development Team
Next review: Before each App Store submission
