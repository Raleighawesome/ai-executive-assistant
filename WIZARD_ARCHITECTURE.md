# Setup Wizard Architecture

## Component Hierarchy

```
src/pages/setup.astro
├── BaseLayout (Astro)
│   ├── Header
│   └── Footer
└── SetupWizard (React Island, client:load)
    ├── WizardStep (Step 1: Platform)
    ├── WizardStep (Step 2: AI Provider)
    ├── WizardStep (Step 3: Modules)
    ├── WizardStep (Step 4: Preferences)
    └── WizardStep (Step 5: Generate)
```

## State Management Flow

```
User Action
    ↓
SetupWizard Component
    ↓
wizardState.set() (nanostores)
    ↓
localStorage (persistent)
    ↓
Re-render with new state
```

## Deep Linking Flow

```
URL Hash Change (#platform, #ai-provider, etc.)
    ↓
useEffect() detects hash
    ↓
currentStep.set(stepNumber)
    ↓
Wizard shows corresponding step
```

## Generation Flow

```
User clicks "Download Configuration"
    ↓
generateConfigYAML() creates config.yaml content
    ↓
generatePromptTemplate() creates prompt template
    ↓
JSZip packages files + README
    ↓
Blob created and downloaded via DOM
```

## File Output Structure

```
ai-assistant-config.zip
├── config.yaml
├── prompts/
│   └── meeting-summary.md
└── README.md
```

## State Schema

```typescript
interface WizardState {
  platform: 'obsidian' | 'logseq' | 'markdown' | 'custom' | null;
  aiProvider: 'openai' | 'vertex' | 'anthropic' | 'ollama' | 'custom' | null;
  modules: {
    foundation: boolean;           // Always true
    meetingProcessing: boolean;
    ragSearch: boolean;
    calendar: boolean;
    automation: boolean;
  };
  preferences: {
    vaultPath: string;
    meetingsFolder: string;
    transcriptsFolder: string;
    peopleFolder: string;
    templatesFolder: string;
    summaryStyle: 'concise' | 'detailed';
    actionItemFormat: string;
  };
}
```

## URL Hash Navigation

| Hash | Step | Description |
|------|------|-------------|
| `#platform` | 1 | Platform selection |
| `#ai-provider` | 2 | AI provider selection |
| `#modules` | 3 | Module selection |
| `#preferences` | 4 | Preferences configuration |
| `#generate` | 5 | Generate and download |

## Styling Architecture

All styling uses Tailwind utility classes that reference CSS variables defined in `src/styles/global.css`:

```css
@theme {
  --color-background: #0a0a0a;
  --color-surface: #141414;
  --color-accent: #3b82f6;
  /* etc */
}
```

This ensures consistency with the dark theme across the entire site.
