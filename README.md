# NexusIQ – AI Coach for League of Legends

NexusIQ is an experimental AI coach for League of Legends players.  
The goal: turn raw match data into actionable insights about your macro, micro and decision-making – so you can climb smarter, not just play more.

## What NexusIQ aims to do

- Analyze your games with AI instead of static stats pages
- Highlight recurring mistakes (positioning, objective calls, wave management)
- Suggest concrete next steps to improve, tailored to your role and elo
- Serve as a long-term coach that tracks your progress over time

> ⚠️ **Status:** Early prototype / work in progress. Expect breaking changes and missing features.

## Tech Stack

- Python backend (AI-driven analysis logic)
- Containerized via Docker & `compose.yaml` for local development

## Getting Started (dev)

```bash
git clone https://github.com/jasonbdt/nexus-iq.git
cd nexus-iq
docker compose up --build
```

Once running, you’ll have the base backend for the future League of Legends AI coach.
Contributions, ideas and feedback on the coaching approach are very welcome.