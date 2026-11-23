## Problem Statement

Customers can't sign in with a magic link.

## Solution

Send a one-time link by email that signs the customer in.

## User Stories

1. As a customer, I want to sign in with a link, so that I don't need a password

## Implementation Decisions

- Links expire after 15 minutes.
- A link is single use.

## Testing Decisions

- Test through the sign-in endpoint.

## Out of Scope

- Passwordless sign-up.

## Further Notes

None.
