# Pending policy — overtime beyond the first hour

Confirmed behavior ends at this boundary:

- close at or before the tolerance limit: 0 overtime minutes;
- close after the tolerance limit: overtime triggered, minimum 60 minutes;
- any additional accumulation or rounding after that minimum: **PENDING USER
  DEFINITION**;
- Sunday policy: **PENDING USER DEFINITION**.

TIME-001 deliberately does not infer proportional, hourly-block, ceiling,
floor, grace-period or partial-hour rules.
