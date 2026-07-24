<div align="center">

# ResumeForge

**Agentic AI-Powered Resume & Cover Letter Builder**

[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=white)](https://react.dev)
[![Vite](https://img.shields.io/badge/Vite-8-646CFF?logo=vite&logoColor=white)](https://vitejs.dev)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-4-06B6D4?logo=tailwindcss&logoColor=white)](https://tailwindcss.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)

*Launch your career with AI-crafted, ATS-optimized resumes and personalized cover letters.*

</div>

---

## Overview

ResumeForge is a modern web application that transforms your career history into polished, job-specific resumes and cover letters. Upload an existing CV or build from scratch, paste a job description, and let AI do the heavy lifting.

## Features

- **CV Upload** — Drag-and-drop or file picker support for PDF, DOCX, and TXT files with intelligent content extraction
- **Manual Entry** — Build your resume from scratch with structured fields for experience, education, and skills
- **Job Description Matching** — Paste any job posting to generate tailored, ATS-optimized documents
- **Glass-Morphism UI** — Modern, responsive design with video background and ambient visual effects
- **Mobile-First** — Fully responsive navigation and layout across all device sizes

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | React 19 |
| Build Tool | Vite 8 |
| Styling | Tailwind CSS 4 |
| Icons | Lucide React |
| Video Streaming | HLS.js |
| Linting | Oxlint |

## Getting Started

### Prerequisites

- [Node.js](https://nodejs.org/) (v18 or later)
- npm or yarn

### Installation

```bash
git clone https://github.com/MarwanAbdellah/tips_hindawi_final.git
cd tips_hindawi_final
npm install
```

### Development

```bash
npm run dev
```

Opens at [http://localhost:5173](http://localhost:5173).

### Build

```bash
npm run build
npm run preview
```

## Project Structure

```
src/
├── main.jsx                  # App entry point
├── App.jsx                   # Root layout (Nav + Hero + Input + Footer)
├── index.css                 # Global styles & Tailwind config
├── assets/
│   └── hero.png              # Hero background image
└── components/
    ├── Navigation.jsx        # Responsive nav with mobile menu
    ├── HeroSection.jsx       # Hero container
    ├── HeroContent.jsx       # Headline, description & CTA
    ├── VideoBackground.jsx   # HLS video player with gradient overlay
    ├── LiquidGlassCard.jsx   # Floating glass-morphism card
    ├── GridLines.jsx         # Decorative vertical grid
    ├── CentralGlow.jsx       # Ambient SVG glow effect
    └── InputSection.jsx      # CV upload / manual entry / job description form
```

## Planned: CrewAI Integration

ResumeForge will integrate [CrewAI](https://github.com/crewAIInc/crewAI) to power multi-agent document generation:

### Agent Architecture

```
┌─────────────────────────────────────────────────┐
│                 CrewAI Orchestrator              │
├─────────────┬───────────────┬───────────────────┤
│  Analyzer   │  Optimizer    │  Generator        │
│  Agent      │  Agent        │  Agent            │
├─────────────┼───────────────┼───────────────────┤
│ Extract     │ ATS keyword   │ Produce final     │
│ skills,     │ matching &    │ resume & cover    │
│ experience, │ content       │ letter in         │
│ education   │ refinement    │ polished format   │
└─────────────┴───────────────┴───────────────────┘
```

### Planned Capabilities

- **Resume Analyzer Agent** — Parses uploaded CVs and extracts structured data (skills, roles, achievements)
- **Job Matching Agent** — Compares candidate profile against job descriptions to identify gaps and alignment
- **Cover Letter Writer Agent** — Generates personalized cover letters with role-specific storytelling
- **Resume Optimizer Agent** — Rewrites bullet points for impact, quantifies achievements, and ensures ATS compatibility
- **Formatting Agent** — Applies clean, recruiter-friendly formatting to final documents

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m "Add your feature"`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Open a Pull Request

## License

This project is licensed under the [MIT License](./LICENSE).
