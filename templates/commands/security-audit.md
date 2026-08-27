# /security-audit - OWASP Security Audit

## Description
Executes the OWASP Top 10 security checklist against this project's codebase.

## Usage
```
/security-audit [scope]
```

**Scope:** $ARGUMENTS

- No scope: Full audit
- Scope: specific domain (e.g., `auth`, `billing`, `exam-management`)

## Process

### Step 1: Load Checklists
Use the Read tool to load these reference files before proceeding:
- `.memory/references/owasp-top10-checklist.md`
- `.memory/references/per-user-isolation.md`
- `.memory/references/laravel-security.md`

### Step 2: Execute Checks

Work through the OWASP Top 10 checklist loaded in Step 1 from `.memory/references/owasp-top10-checklist.md`.

For each category (A01-A10):
1. Read the verification steps from the checklist
2. Execute each check against the codebase (use Grep, Glob, Read tools)
3. For per-user isolation checks, also reference `.memory/references/per-user-isolation.md`
4. For Laravel-specific checks, also reference `.memory/references/laravel-security.md`
5. Record findings with severity (Critical/High/Medium/Low) and file:line references

### Step 3: Generate Report
```markdown
## Security Audit Report
Date: [date]
Scope: [full / specific domain]
Auditor: security-audit

### Summary
| Category | Status | Findings |
|----------|--------|----------|
| A01: Broken Access Control | PASS/WARN/FAIL | [count] |
| A02: Cryptographic Failures | PASS/WARN/FAIL | [count] |
| ... | ... | ... |

### Critical Findings
[List with file:line references]

### High Findings
[List with file:line references]

### Recommendations
[Prioritized action items]
```
