# Tool Comparison

## Task

I used Cursor for a bounded Day 4 task: understanding and cleaning up the service flow. The main thing Cursor helped with was turning the request flow into simple Mermaid diagrams so I could see how `routes.py`, `models.py`, `service.py`, `policy_client.py`, and `repository.py` connect.

## Cursor

Cursor was helpful because it stayed close to the files in VS Code. I could look at the route file, ask questions, and use the diagram to understand the flow from `POST /notifications` to validation, policy lookup, rule checks, repository recording, and the final response.

Cursor was awkward when I needed to connect the work back to the full rubric. I still had to be careful that the diagrams and notes matched the contract instead of just looking correct visually.

## Preference

For understanding flow, diagrams, and small local edits, I would use Cursor because it works directly beside the code and makes the service easier to reason about visually.
