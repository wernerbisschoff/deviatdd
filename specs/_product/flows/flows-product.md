## FLOW-01 Flows
- Actor: Developer
- Domain: Software Engineering
- Status: Active

### Problem / job to be done
- Creation of AI assisted user flows (like this one)

### Trigger
- User runs /deviate-flows in their agent of choice

### Preconditions
- User has an idea of how the product should be used by customers

### Happy path (primary steps)
1. The user runs the /deviate-flows command/skill.
2. The agent converses with the user to determine core customer flows
3. The agent outputs a flows.md or flows-<domain>.md in the specs/_product/ dir
4. The agent creates/updates the specs/flows/index.md 
4. The flows are used and referenced by id during lower layers to ensure no context is lost in smaller layers

### Alternate / error paths
TBD

### Success State
- A new flows.md or flows-<domain>.md in the specs/_product/ dir of the repo
- The new flows are added to the specs/flows/index.md

### Metrics / Signals
- Flows get referenced by ID throughout the DeviaTDD workflow, in the Macro, Meso, and Micro layers
- Flows get correctly referenced whether they are in a general flows.md file or in a dedicated flows-<domain>.md file
- All flow IDs added to specs/flows/index.md, with name, actor, domain, status, and source

## FLOW-02 Architecture
- Actor: Developer
- Domain: Software Engineering
- Status: Active

### Problem / job to be done
- Product level architecture that spans across epics

### Trigger
- User runs /deviate-architecture in their agent of choice

### Preconditions
- User has an idea of how the product should be architected
- User flows exist in specs/flows/

### Happy path (primary steps)
1. User runs /deviate-architecture command/skill
2. The agent converses with the user to determine the architectural design of the product
3. The agent maintains or creates cross-epic architecture

### Alternate / error paths
TBD

### Success State
- A new architecture.md is written in specs/_product/, or an existing one is updated
- A new domain_model.md is written in specs/_product/, or an existing one is updated

### Metrics / Signals
- Product level architecture only
- Respects the constition if exists
- Classification of requested change as Local/Context-Bridging/Context-Creating

## FLOW-03 Release
- Actor: Developer
- Domain: Software Engineering
- Status: Active

### Problem / job to be done
- Definition of next coherent release as a slice of flows and epics that makes sense for users and for the business

### Trigger
- User runs /deviate-release in their agent of choice

### Preconditions
- Architecture exists
- Flows exist

### Happy Path (Primary Steps)
1. User runs /deviate-release with a release goal description
2. The agent compiles release information from user flows and optionally epics
3. The agent writes to specs/_product/release-next.md, overriding the previous release
4. Subsequent prompts and phases refer to the release file when deciding what the next epic should be

### Alternate / Error Paths
TBD

### Success State
- A new or updated specs/_product/release-next.md 

### Metrics / Signals
- Downstream /deviate-explore and other prompts reference the release file as a guiding compass
