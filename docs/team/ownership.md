# Choose one of five parts

The five teammates choose Person 1 through Person 5 themselves. A numbered part
describes responsibility, not an assigned individual. There is no sixth
development or coordination role for the project owner.

| Part | Responsibility | Main boundary | Individual |
| --- | --- | --- | --- |
| [Person 1](person_1.md) | Inference engine and model runtime | Reusable pose and temporal inference | Unassigned |
| [Person 2](person_2.md) | API jobs incidents and private results | api/ and session/report orchestration | Unassigned |
| [Person 3](person_3.md) | Public frontend and demo experience | frontend/ and presentation | Unassigned |
| [Person 4](person_4.md) | Dataset evaluation benchmarks and evidence | evaluation/, tools, research/, examples/ | Unassigned |
| [Person 5](person_5.md) | Deployment security integration and release | deployment/, configs/, CI, release docs | Unassigned |

See the [unassigned roster](roster.md). Agree the choices as a group, then update
the Individual column and GitHub review rules. Roster order does not map to parts.

Person 5 maintains the board, integration order, release checklist, final README,
and combined academic report. The other four supply their component and report
sections. Person 5 coordinates rather than implementing everyone else's work.

Persons 1 and 2 agree runtime interfaces; Persons 2 and 3 agree the API. Person 4
approves metric claims and example provenance. Persons 2 and 5 agree public
upload limits, ownership, cleanup, and retention.

After selection, Person 5 creates the starter issues and fills CODEOWNERS with
the chosen reviewers once repository access is accepted. Until then request
reviewers manually. Changes spanning parts need review from each affected part.

Person 5 arranges required repository/hosting permissions with the account
holder. Account access is not a sixth implementation workstream.
