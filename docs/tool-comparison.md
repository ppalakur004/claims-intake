# Tool Comparison

## Task

I used Cursor for one bounded Day 4 task: reviewing the README run instructions and checking whether a new person could follow them to start the service, send a request, run tests, and build the Docker image.

## Cursor

Cursor made the small editing task easy because the README was open next to the chat, so I could ask for wording changes and immediately see the exact lines being changed. That felt useful for local cleanup work where the goal was clear and the file was already in front of me.

Cursor was more awkward when the task needed the whole assignment context. I had to keep the rubric and contract details in mind myself, especially the platform note and the requirement that the README assumes the reader is already inside the container.

## Codex

Codex was stronger for connecting multiple files. It was easier to reason across `api/routes.py`, `service.py`, `policy_client.py`, the contract, and the route tests in one flow. That helped more for deciding whether the HTTP responses matched the rules and status codes.

Codex was less convenient for tiny wording edits because I was not directly working inside the editor view the same way. For very small document polish, that extra distance made Cursor feel faster.

## Preference

For small local edits in one file, especially README wording, I would use Cursor because the editor context is immediate.

For contract-driven implementation or tests that need several files to agree, I would use Codex because it is better at keeping the whole service flow and rubric in view.
