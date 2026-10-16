# 2026F AI Course Plan and Repository Development Guide

> This document summarizes the course plan provided by Prof. Jinn-Liang Liu and explains how this repository should evolve throughout the semester.
>
> The purpose of this document is to give developers and AI coding agents such as Codex enough context to understand:
>
> 1. What this course is trying to accomplish.
> 2. What the three course projects are.
> 3. What AI/deep-learning topics will be covered.
> 4. What the current Docker/openpilot environment represents.
> 5. How future course work should be added to this repository.
> 6. Which existing components should remain stable unless modification is explicitly required.

---

# 1. Course Information

Course:

**2026F AI**

Department:

**Department of Power Mechanical Engineering, National Tsing Hua University**

Instructor:

**Prof. Jinn-Liang Liu (劉晉良)**

Class time:

- Fridays
- 12:10 PM – 3:10 PM
- 2026/09/11 – 2026/12/18
- No class on 2026/09/25 and 2026/10/09

Location:

**Engineering Building I (工一), Room 108**

Office hours:

- Fridays
- 3:10 PM – 4:30 PM
- Engineering Building I Room 108
- or online by appointment

The four major themes of the course are:

1. **Algorithm**
2. **Big Data**
3. **Coding**
4. **Deployment**

---

# 2. Important Copyright Notice

The original course planning document states:

> Do Not Distribute this or Make it a Public Link. All Rights Reserved.

Therefore:

- Do NOT commit the professor's original course document to a public repository.
- Do NOT upload or redistribute professor-provided copyrighted course materials unless permission has been granted.
- Do NOT automatically copy professor-provided files into public Git history.
- This document is intended as an internal project-development summary.
- When adding future professor-provided assets, verify whether they may be redistributed before committing them.

This rule also applies to future course materials unless explicitly stated otherwise.

---

# 3. Course Projects

The semester contains three main projects.

## Project 1 — Install Ubuntu and OpenPilot

Professor's plan:

> Install Ubuntu 24.04 and OP
> (dataB6, dataC, aJLL, VSC, Q&A)

The purpose of Project 1 is to establish the OpenPilot development/replay environment.

Important components include:

- Ubuntu 24.04 in the original course plan
- OpenPilot
- dataB6
- dataC
- aJLL
- Visual Studio Code
- Q&A / troubleshooting

### Current repository implementation

This repository currently uses a Docker-based environment on macOS instead of replacing the host operating system with Ubuntu.

The working architecture is approximately:

```text
macOS host
    │
    ▼
Docker Desktop
    │
    ├── compute container
    │
    └── display container
            │
            ▼
        VNC / noVNC
```

The containers use a Linux environment for OpenPilot.

The current OpenPilot baseline is:

```text
OpenPilot v0.9.1
```

The currently validated environment includes:

- OpenPilot source/environment
- OpenPilot build artifacts
- OpenPilot UI
- official OpenPilot replay
- professor/JLL replay tools
- Taiwan dataC replay
- USA JLL demo replay
- dataB6
- aJLL reference material
- VNC/noVNC display
- Docker health checks

Project 1 should therefore be treated as the current **baseline environment**.

Do not unnecessarily redesign or replace this environment while implementing later course projects.

---

# 4. Current Docker Architecture

The current project uses four important Docker volumes:

```text
ai-self-driving-car_openpilot-repo
ai-self-driving-car_replay-data
ai-self-driving-car_op-socket
ai-self-driving-car_op-runtime
```

Their responsibilities are different.

## 4.1 openpilot-repo

Mounted approximately as:

```text
/opt/openpilot
```

Purpose:

- OpenPilot v0.9.1 source
- OpenPilot build results
- professor-provided tools
- tools092
- dataC-related OpenPilot replay assets
- replayJLL
- replayJLL.compat
- official OpenPilot tools backup
- other OpenPilot runtime/build files

This volume represents the working OpenPilot baseline.

Avoid manually modifying source code inside this volume unless modification of OpenPilot itself is required by a later assignment.

---

## 4.2 replay-data

Mounted approximately as:

```text
/data
```

Purpose:

- large replay datasets
- dataB6

The current dataB6 dataset is approximately 2.8 GB.

Large datasets should remain outside normal Git history.

Do NOT copy large datasets into the repository simply so they can be committed.

---

## 4.3 op-socket

Mounted approximately as:

```text
/run/openpilot
```

Purpose:

- communication between Docker services
- health/runtime socket communication

Example:

```text
/run/openpilot/replay.sock
```

This is runtime infrastructure rather than course source code.

---

## 4.4 op-runtime

Mounted approximately as:

```text
/tmp
```

Purpose:

- shared runtime state
- OpenPilot runtime communication
- VisionIPC-related resources
- other temporary IPC/runtime resources required by compute/display processes

This is also runtime infrastructure.

---

# 5. Repository vs Docker Volumes

An important architectural distinction must be maintained.

## Git repository

The repository should contain:

```text
environment definitions
Docker configuration
scripts
documentation
student-written source code
models
algorithms
AI agents
robot code
integration code
reproducibility logic
```

## Docker volumes

Docker volumes currently contain:

```text
OpenPilot working environment
OpenPilot build artifacts
large datasets
runtime state
IPC resources
```

Therefore, the absence of the full OpenPilot source tree or dataB6 from the host repository is intentional.

Conceptually:

```text
GitHub repository
       │
       ├── How the environment is built
       ├── How the environment is operated
       ├── Student source code
       └── Documentation
                │
                ▼
             Docker
                │
        ┌───────┴────────┐
        ▼                ▼
 /opt/openpilot        /data
        │                │
 OpenPilot baseline    datasets
```

---

# 6. Development Principle for the Semester

The main development rule is:

> Keep the validated OpenPilot environment as a stable baseline and place new student-developed algorithms, models, agents, and integration code in Git-tracked repository directories.

Do NOT use the Docker volume as the primary location for new student source code.

Bad:

```text
/opt/openpilot/random_student_model.py
```

when the only copy exists inside a Docker volume.

Better:

```text
repository/models/my_model/model.py
```

and mount or integrate that source into Docker.

The reason is simple:

```text
Git-tracked code
    ↓
history
    ↓
diff
    ↓
rollback
    ↓
reproducibility
```

while:

```text
manual modification inside Docker volume
    ↓
not necessarily tracked
    ↓
easy to forget
    ↓
easy to lose
    ↓
difficult to reproduce
```

---

# 7. Recommended Repository Evolution

As the semester progresses, the repository may evolve toward:

```text
ai-self-drive-car-ws/
│
├── docker/
│   ├── Dockerfile.compute
│   ├── Dockerfile.display
│   ├── docker-compose.yaml
│   └── ...
│
├── scripts/
│   ├── openpilot.sh
│   ├── validate-docker.sh
│   ├── build-jll-compatible.sh
│   └── ...
│
├── docs/
│   ├── COURSE_PLAN.md
│   ├── IMPLEMENTATION.md
│   ├── INSTALLOP_AUDIT.md
│   └── ...
│
├── projects/
│   ├── project1/
│   ├── project2/
│   │   └── ai_agent/
│   └── project3/
│       └── robot/
│
├── models/
│   ├── cnn/
│   ├── rnn/
│   ├── transformer/
│   └── ...
│
├── algorithms/
│   └── ...
│
├── integration/
│   └── ...
│
└── README.md
```

These directories do NOT need to be created before they are actually needed.

Avoid creating empty architecture only for appearance.

Create directories when corresponding coursework begins.

---

# 8. Part II — Lecture Topics

The professor's planned lecture sequence is summarized below.

---

## Topic 1 — AI & OpenPilot

Topics include:

- AI
- OpenPilot
- historical development of industrial technology
- development from mechanical power to electrical power, digital technology, and intelligent systems
- algorithms
- applications of AI

Historical algorithm references include:

- M. Al-Khwārizmī
- Isaac Newton
- Ada Lovelace

OpenPilot serves as an important applied AI platform throughout the course.

---

## Topic 2 — AI Basics

Topics include:

- Source
- MNIST
- Image Recognition
- Softmax Regression
- Cross Entropy
- Gradient Descent
- Back Propagation
- Computational Graph

The course notes associate basic Softmax Regression with approximately:

```text
92%
```

on the discussed MNIST example.

Possible future repository work may include introductory implementations or experiments involving:

```text
models/
experiments/
notebooks/
```

Do not assume these directories or implementations are required until the corresponding assignment is given.

---

# 9. Deep Learning and CNN

Topics include:

- Deep Learning
- ReLU
- Learning Rate
- Overfitting
- Dropout
- Convolutional Neural Network (CNN)

The course notes reference example performance progression such as:

```text
Deep Learning      ~98%
Dropout            ~98.2%
CNN                ~99.3%
```

These values belong to the professor's course outline/examples and should not automatically be interpreted as required performance targets for student implementations.

When implementing CNN-related coursework, student source should normally live in Git-tracked directories such as:

```text
models/cnn/
```

Example conceptual structure:

```text
models/cnn/
├── model.py
├── dataset.py
├── train.py
├── evaluate.py
└── inference.py
```

Actual structure should follow assignment requirements rather than this example if the professor specifies something different.

---

# 10. Recurrent Neural Networks

Topics include:

- Batch Normalization
- MNIST
- RNN
- Deep RNN
- Long Short-Term Memory (LSTM)
- Gated Recurrent Network
- RNN Language Models
- Vanishing Gradient

The course outline references:

```text
Batch Normalization ~99.5%
MNIST Record / Kaggle ~100%
```

Again, these are course-outline references and should not automatically be treated as required project metrics.

Possible future implementation area:

```text
models/rnn/
```

---

# 11. Attention, Transformer, and LLM

Topics include:

- Attention
- Transformer
- LLM
- Transformers in LLMs
- Attention in Transformers
- AI Software

Possible future work may include:

```text
models/transformer/
projects/project2/ai_agent/
```

Do not prematurely introduce a large LLM framework unless it is required by the course assignment.

Prefer the simplest implementation that satisfies the current course objective.

---

# 12. Theory of Deep Learning

The course also includes theoretical foundations.

Topics include:

## Gradient Descent and Backpropagation

Study:

- optimization
- gradients
- backpropagation

## Automatic Differentiation

Study:

- forward mode
- reverse mode
- Jacobian

## Convolution

Study the mathematical and computational role of convolution.

## Batch Normalization

The outline connects Batch Normalization with:

```text
Preconditioning
```

Implementations should preserve the connection between mathematical concepts and actual code.

---

# 13. OpenPilot-Specific Topics

Later in the semester, the course returns to OpenPilot.

Planned topics include:

- OPNN
- sim_output
- comma.ai
- comma two
- OPCoding
- OPWare

This is the point where modifications or deeper integration with OpenPilot may become necessary.

Until an assignment requires such modifications, the current OpenPilot v0.9.1 environment should remain a stable baseline.

---

# 14. What To Do If OpenPilot Source Must Be Modified

If future coursework requires modifying:

```text
selfdrive/
cereal/
tools/
OPNN
OpenPilot process configuration
OpenPilot message interfaces
planning/control/perception pipeline
```

do NOT rely solely on manual edits inside:

```text
/opt/openpilot
```

because `/opt/openpilot` is stored in a Docker volume.

Instead, create a reproducible Git-tracked mechanism.

Possible strategies include:

### Strategy A — Patch

```text
patches/
└── openpilot/
```

Apply patches during environment setup.

### Strategy B — Overlay

```text
openpilot-overlay/
```

Store replacement/added source files in Git and copy/mount them into the OpenPilot environment.

### Strategy C — Fork

If modifications become extensive, maintain a dedicated OpenPilot fork.

The appropriate strategy should be chosen only when modification becomes necessary.

Do not prematurely fork OpenPilot.

---

# 15. Project 2 — AI Agent

Professor's course plan describes Project 2 as:

> Do Steps 5-6 (Q&A) and AI Agent

The detailed technical requirements of the AI Agent are NOT fully specified in the course-plan document.

Therefore:

**Do not invent Project 2 requirements based only on this document.**

When the professor provides Steps 5–6 or additional Project 2 instructions:

1. preserve the original requirements;
2. document them;
3. implement them in a Git-tracked location;
4. integrate with the existing Docker/OpenPilot baseline only where required.

Recommended conceptual location:

```text
projects/project2/
└── ai_agent/
```

This path is a repository design recommendation, not a professor-mandated path.

---

# 16. Project 3 — AI Robot

Professor's course plan describes Project 3 as:

> Do AI Robot (Run1-2)

The course-plan document does not contain enough information to determine exactly what Run1 and Run2 require.

Therefore:

**Do not invent the AI Robot architecture yet.**

Wait for the corresponding professor-provided instructions.

When Project 3 begins, a possible repository location is:

```text
projects/project3/
└── robot/
```

Again, this is a repository organization recommendation rather than an official course requirement.

---

# 17. Reports and Deadlines

The professor requires project reports to be submitted as PDF demonstrations.

The original course plan lists:

```text
Report 1: 2026/10/23
Report 2: 2026/11/27
Report 3: 2026/12/25
```

The course document also specifies an email submission format.

When preparing reports:

- generate PDF output;
- verify the correct report number;
- verify student information;
- follow the professor's required email subject format;
- do not automatically send email unless explicitly requested by the user.

Potential repository organization:

```text
reports/
├── report1/
├── report2/
└── report3/
```

Avoid committing private student information into a public repository.

---

# 18. Part III — Demos and Videos

The professor's outline includes demonstrations/videos involving:

## OpenPilot

Material from years including:

- 2026
- 2024
- 2023
- 2020
- 2016

## CB

Material from years including:

- 2024
- 2023
- 2021

## Tesla / Waymo

Material from years including:

- 2026
- 2025
- 2019
- 2016

These are course references/demonstrations.

Do not assume that every demo corresponds to a required implementation.

---

# 19. Current Development Policy

For all future work in this repository, follow these rules.

## Rule 1 — Preserve the working Project 1 baseline

The existing Docker/OpenPilot environment has already required substantial compatibility work.

Do not refactor it without a concrete reason.

---

## Rule 2 — New student code belongs in Git

Examples:

```text
models/
algorithms/
projects/
integration/
```

New code should normally be:

```text
write
↓
test
↓
git diff
↓
commit
↓
continue
```

---

## Rule 3 — Large datasets do not belong in normal Git history

Examples:

```text
dataB6
large replay files
large model checkpoints
```

Use appropriate local/external storage.

Do not accidentally commit multi-GB datasets.

---

## Rule 4 — Docker volumes are not source-control systems

A Docker volume can persist data, but it does not replace Git.

Never assume:

```text
"It is inside the Docker volume, therefore it is safely version controlled."
```

That is false.

---

## Rule 5 — Do not casually modify the OpenPilot baseline

Before modifying `/opt/openpilot`, ask:

```text
Can this functionality be implemented as student-owned code outside OpenPilot?
```

If yes:

```text
implement outside OpenPilot
        ↓
Git track it
        ↓
integrate through a defined interface
```

If no:

```text
determine required OpenPilot modification
        ↓
make modification reproducible
        ↓
Git track patch/overlay/fork
```

---

## Rule 6 — Follow the professor's progression

Do not over-engineer future assignments before their requirements are known.

Expected progression:

```text
Project 1
OpenPilot environment
        ↓
AI fundamentals
        ↓
Deep Learning
        ↓
CNN
        ↓
RNN
        ↓
Attention / Transformer / LLM
        ↓
Deep Learning theory
        ↓
OpenPilot-specific AI
        ↓
Project 2
AI Agent
        ↓
Project 3
AI Robot
```

The repository should evolve along with this progression.

---

# 20. Guidance for Codex and Other Coding Agents

When working on this repository, an AI coding agent MUST first determine whether a requested change belongs to:

```text
A. Environment infrastructure
B. Professor/OpenPilot baseline
C. Dataset
D. Student-developed source code
E. Documentation
```

Use the following decision process:

```text
New request
    │
    ▼
Does it require changing OpenPilot itself?
    │
 ┌──┴──┐
 No    Yes
 │      │
 ▼      ▼
Implement in       Is the modification
student-owned      actually necessary?
Git source               │
                    ┌────┴────┐
                    No       Yes
                    │         │
                    ▼         ▼
                keep OP    create a
                baseline   reproducible
                intact     Git-tracked
                           modification
```

Before editing Docker infrastructure, Codex should inspect:

```text
README.md
docs/IMPLEMENTATION.md
docs/INSTALLOP_AUDIT.md
docs/INSTALLOP_ASSETS.md
docker/docker-compose.yaml
scripts/openpilot.sh
scripts/validate-docker.sh
```

Do not replace a known-working solution merely because another architecture appears cleaner.

Stability and reproducibility are more important than unnecessary refactoring.

---

# 21. Current Baseline Status

At the time this document was created, the Project 1 environment had reached approximately the following state:

```text
OpenPilot v0.9.1 environment        DONE
Docker compute container            DONE
Docker display container            DONE
Container health checks             DONE
OpenPilot UI                        DONE
Official replay                     DONE
JLL compatibility solution          DONE
Taiwan dataC replay                 DONE
Taiwan visual replay                DONE
USA JLL demo replay                 DONE
USA visual replay                   DONE
dataB6                              PRESENT
aJLL                                PRESENT / REFERENCE
VNC / noVNC                         DONE
Validation script                   PASS
```

The current validated Docker volumes are:

```text
ai-self-driving-car_openpilot-repo
ai-self-driving-car_replay-data
ai-self-driving-car_op-socket
ai-self-driving-car_op-runtime
```

Do not remove these volumes casually.

In particular, avoid destructive commands such as:

```bash
docker compose down -v
```

unless volume deletion is explicitly intended.

---

# 22. Known Remaining Infrastructure Question

One engineering question remains separate from normal coursework:

```text
fresh clone
    +
empty Docker volumes
    ↓
complete reconstruction
    ↓
same working environment?
```

The currently working environment has been validated, but complete fresh-volume reproducibility should be treated as a separate infrastructure test.

Do not destroy the current working volumes simply to test this.

Any future reproducibility test should use isolated/new Docker volumes.

---

# 23. Semester Development Strategy

The intended development strategy is:

```text
CURRENT
Project 1 baseline
OpenPilot + Docker + datasets
        │
        ▼
FREEZE STABLE BASELINE
        │
        ▼
Follow course lectures
        │
        ▼
Implement new concepts
        │
        ▼
Add student code to repository
        │
        ▼
Test
        │
        ▼
Commit
        │
        ▼
Integrate with OpenPilot only when needed
        │
        ▼
Project 2
        │
        ▼
Project 3
```

In short:

> The existing OpenPilot/Docker environment is the course platform. Future models, algorithms, agents, and robot code should normally be developed as Git-tracked source code on top of that platform rather than by continuously modifying the baseline Docker volume.

---

# 24. Source of Truth

When requirements conflict or are unclear, use the following priority:

```text
1. Latest explicit instructions from the professor
2. Original professor-provided assignment/course documents
3. Existing validated repository documentation
4. Existing working implementation
5. Reasonable engineering assumptions
```

Engineering assumptions must never silently replace professor requirements.

If the course material does not specify something, document that it is an implementation decision rather than presenting it as a professor requirement.

---

# 25. Summary for Codex

Before making significant changes, remember:

```text
Professor's course
        │
        ▼
Algorithm + Big Data + Coding + Deployment
        │
        ▼
Project 1
OpenPilot environment
        │
        │  CURRENT BASELINE
        ▼
AI / Deep Learning coursework
        │
        ├── CNN
        ├── RNN
        ├── Transformer
        └── DL Theory
        │
        ▼
OpenPilot-specific AI
        │
        ▼
Project 2
AI Agent
        │
        ▼
Project 3
AI Robot
```

The repository should evolve with the course.

**Preserve the validated baseline.**

**Put new student source code under Git version control.**

**Do not use Docker volumes as a substitute for Git.**

**Do not put large datasets into normal Git history.**

**Do not modify OpenPilot itself unless the task actually requires it.**

**If OpenPilot must be modified, make the modification reproducible and Git-tracked.**

**Do not invent requirements that are not present in professor-provided material.**
