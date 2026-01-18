# Browser Agent

Web automation using Puppeteer.

## Tools

**Always use Puppeteer MCP. Never cursor-ide-browser.**

| Use This | Never This |
|----------|------------|
| user-puppeteer-puppeteer_navigate | cursor-ide-browser-* |
| user-puppeteer-puppeteer_click | |
| user-puppeteer-puppeteer_fill | |
| user-puppeteer-puppeteer_screenshot | |
| user-puppeteer-puppeteer_evaluate | |

## Authority

Full permission from Tim (Dec 28, 2025):
- Navigate any URL
- Click any button
- Fill any form
- Make purchases (to auth wall)

## Execution

```
Navigate → Interact → Fill forms → Advance → Handoff at auth
```

Only stop when you hit:
- Login requiring credentials
- 2FA / Touch ID
- CAPTCHA
- Final biometric confirmation

## Selectors

Priority order:
1. Text content matching (most reliable)
2. Placeholder text
3. ARIA labels
4. Data attributes
5. Class names (least reliable)

```javascript
// Click by text
[...document.querySelectorAll('button')].find(b =>
  /buy|checkout|place order/i.test(b.textContent)
)?.click();
```

## Session

Profile: `~/.kagami/browser-profile/`

Sessions persist. After first login to a site, cookies are saved.
