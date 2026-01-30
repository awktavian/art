#!/usr/bin/env python3
"""
Upload Automation Assessment Rubric to Google Sheets via Composio

Uses the Composio Google Sheets integration to create a public spreadsheet.
"""

import asyncio
import sys
sys.path.insert(0, '/Users/schizodactyl/projects/kagami')

from kagami.core.services.composio import get_composio_service

# Data to upload
SUMMARY_DATA = [
    ['Code', 'Role', 'Category', 'Automation %', 'Ceiling', 'Status'],
    ['QA', 'Quality Assurance Engineer', 'Quality', '85%', '', 'High'],
    ['ENG', 'Software Engineer', 'Technical', '80%', '', 'High'],
    ['TPM', 'Technical Program Manager', 'Planning', '75%', '', 'High'],
    ['DE', 'Data Engineer', 'Data', '75%', '', 'High'],
    ['PM', 'Product Manager', 'Strategy', '70%', '', 'Medium'],
    ['DS', 'Data Scientist', 'Research', '70%', '', 'Medium'],
    ['Design', 'Product Designer', 'Creative', '70%', '', 'Medium'],
    ['PMM', 'Product Marketing Manager', 'Marketing', '65%', '', 'Medium'],
    ['EM', 'Engineering Manager', 'People', '60%', '75%', 'Low'],
    ['UXR', 'UX Researcher', 'Research', '55%', '', 'Low'],
    ['', 'AVERAGE', '', '68%', '', ''],
]

RUBRIC_DATA = [
    ['Score', 'Classification', 'Criteria', 'Weight'],
    ['3', 'Fully Automated', 'Task performed entirely by AI without human intervention', '100%'],
    ['2', 'Partially Automated', 'AI generates output but requires human review/approval', '66%'],
    ['1', 'AI-Assisted', 'AI provides recommendations but human performs the task', '33%'],
    ['0', 'Human Only', 'Task fundamentally requires human judgment, ethics, or relationship', '0%'],
]

async def main():
    service = await get_composio_service()
    await service.initialize()
    
    print("Creating Google Sheet via Composio...")
    
    # Try to create a spreadsheet
    try:
        # First, let's see what actions are available
        actions = await service.list_actions("googlesheets")
        print(f"Available Google Sheets actions: {actions}")
        
        # Create spreadsheet
        result = await service.execute_action(
            "GOOGLESHEETS_CREATE_SPREADSHEET",
            {
                "title": "AI Workforce Automation Assessment Rubric",
            }
        )
        print(f"Created spreadsheet: {result}")
        
        spreadsheet_id = result.get('spreadsheetId')
        if spreadsheet_id:
            # Add data
            await service.execute_action(
                "GOOGLESHEETS_BATCH_UPDATE",
                {
                    "spreadsheet_id": spreadsheet_id,
                    "range": "Sheet1!A1:F12",
                    "values": SUMMARY_DATA,
                }
            )
            
            print(f"\n✅ Google Sheet created!")
            print(f"URL: https://docs.google.com/spreadsheets/d/{spreadsheet_id}")
            
    except Exception as e:
        print(f"Error: {e}")
        print("\n📋 Manual upload instructions:")
        print("1. Go to https://sheets.google.com")
        print("2. Click 'File > Import'")
        print("3. Upload: /Users/schizodactyl/projects/art/disciplines/automation_assessment_rubric.xlsx")
        print("4. Click 'Share' > 'Anyone with the link'")
        print("5. Copy the link and share")

if __name__ == '__main__':
    asyncio.run(main())
