import React, { useEffect, useState } from 'react';
import { useStore } from '@nanostores/react';
import JSZip from 'jszip';
import { wizardState, currentStep, resetWizard, type WizardState } from '../../stores/wizard';
import { WizardStep } from './WizardStep';

export function SetupWizard() {
  const state = useStore(wizardState);
  const step = useStore(currentStep);
  const [isGenerating, setIsGenerating] = useState(false);

  // Handle deep-linking via URL hash
  useEffect(() => {
    const hash = window.location.hash.slice(1);
    const stepMap: Record<string, number> = {
      platform: 1,
      'ai-provider': 2,
      modules: 3,
      preferences: 4,
      generate: 5,
    };
    if (hash in stepMap) {
      currentStep.set(stepMap[hash]);
    }
  }, []);

  // Update URL hash when step changes
  useEffect(() => {
    const stepHashes = ['', 'platform', 'ai-provider', 'modules', 'preferences', 'generate'];
    window.location.hash = stepHashes[step] || '';
  }, [step]);

  const updateState = (partial: Partial<WizardState>) => {
    wizardState.set({ ...state, ...partial });
  };

  const nextStep = () => {
    if (step < 5) currentStep.set(step + 1);
  };

  const prevStep = () => {
    if (step > 1) currentStep.set(step - 1);
  };

  const canProceed = () => {
    switch (step) {
      case 1:
        return state.platform !== null;
      case 2:
        return state.aiProvider !== null;
      case 3:
        return state.modules.foundation; // Foundation is required
      default:
        return true;
    }
  };

  const generateConfigYAML = (): string => {
    const providerSection =
      state.aiProvider === 'ollama'
        ? `ai_provider: ollama
ai_model: llama3.2
ai_endpoint: http://localhost:11434`
        : state.aiProvider === 'openai'
        ? `ai_provider: openai
ai_model: gpt-4o-mini
ai_endpoint: https://api.openai.com/v1`
        : state.aiProvider === 'anthropic'
        ? `ai_provider: anthropic
ai_model: claude-3-5-sonnet-20241022
ai_endpoint: https://api.anthropic.com`
        : state.aiProvider === 'vertex'
        ? `ai_provider: vertex
ai_model: gemini-1.5-flash
ai_endpoint: us-central1-aiplatform.googleapis.com
gcp_project: your-project-id`
        : `ai_provider: custom
ai_model: your-model
ai_endpoint: http://localhost:8000`;

    return `# AI Executive Assistant Configuration
# Generated on ${new Date().toISOString()}

# Vault paths (relative to vault root)
vault_path: ${state.preferences.vaultPath}
meetings_folder: ${state.preferences.meetingsFolder}
transcripts_folder: ${state.preferences.transcriptsFolder}
people_folder: ${state.preferences.peopleFolder}
templates_folder: ${state.preferences.templatesFolder}

# AI Provider
${providerSection}

# Processing preferences
summary_style: ${state.preferences.summaryStyle}
action_item_format: "${state.preferences.actionItemFormat}"
date_format: "%Y-%m-%d"

# Enabled modules
modules:
  foundation: ${state.modules.foundation}
  meeting_processing: ${state.modules.meetingProcessing}
  rag_search: ${state.modules.ragSearch}
  calendar: ${state.modules.calendar}
  automation: ${state.modules.automation}
`;
  };

  const generatePromptTemplate = (): string => {
    const style = state.preferences.summaryStyle === 'concise' ? 'brief and to the point' : 'comprehensive and detailed';

    return `# Meeting Summary Prompt Template

You are an AI assistant helping process meeting notes. Generate a ${style} summary.

## Instructions

1. **Executive Summary**: Provide a 4-sentence overview of the meeting
2. **Key Topics**: Break down major discussion points with findings and decisions
3. **Action Items**: Extract tasks in the format: ${state.preferences.actionItemFormat}
4. **Attendees**: List participants mentioned in the transcript

## Output Format

### Executive Summary
[Your summary here]

### Key Topics
- **Topic 1**: [Discussion points]
- **Topic 2**: [Discussion points]

### Action Items
${state.preferences.actionItemFormat}

### Attendees
- Person 1
- Person 2
`;
  };

  const downloadZip = async () => {
    setIsGenerating(true);

    // Track download started
    if (typeof window !== 'undefined' && (window as any).umami) {
      (window as any).umami.track('download-click');
    }

    try {
      const zip = new JSZip();

      // Add config file
      zip.file('config.yaml', generateConfigYAML());

      // Add prompt template
      const promptsFolder = zip.folder('prompts');
      if (promptsFolder) {
        promptsFolder.file('meeting-summary.md', generatePromptTemplate());
      }

      // Add README with next steps
      const readme = `# AI Executive Assistant Configuration

This ZIP contains your customized configuration files.

## Next Steps

1. Extract this ZIP to your vault's scripts folder
2. Install dependencies: \`pip install -r requirements.txt\`
3. Follow the documentation for your selected modules:
${state.modules.meetingProcessing ? '   - Meeting Processing: https://ai-executive-assistant.vercel.app/docs/meeting-processing\n' : ''}${state.modules.ragSearch ? '   - RAG Search: https://ai-executive-assistant.vercel.app/docs/rag-search\n' : ''}${state.modules.calendar ? '   - Calendar Integration: https://ai-executive-assistant.vercel.app/docs/calendar\n' : ''}${state.modules.automation ? '   - Automation: https://ai-executive-assistant.vercel.app/docs/automation\n' : ''}
## Platform: ${state.platform}
## AI Provider: ${state.aiProvider}

Visit https://ai-executive-assistant.vercel.app/docs for full documentation.
`;
      zip.file('README.md', readme);

      // Generate and download
      const blob = await zip.generateAsync({ type: 'blob' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'ai-assistant-config.zip';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      // Track setup complete
      if (typeof window !== 'undefined' && (window as any).umami) {
        (window as any).umami.track('setup-complete');
      }
    } catch (error) {
      console.error('Error generating ZIP:', error);
      alert('Failed to generate configuration. Please try again.');
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto">
      <div className="card">
        {/* Progress bar */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-text-secondary">
              Step {step} of 5
            </span>
            <span className="text-sm text-text-muted">{Math.round((step / 5) * 100)}%</span>
          </div>
          <div className="h-2 bg-surface rounded-full overflow-hidden">
            <div
              className="h-full bg-accent transition-all duration-300"
              style={{ width: `${(step / 5) * 100}%` }}
            />
          </div>
        </div>

        {/* Step 1: Platform */}
        <WizardStep
          stepNumber={1}
          currentStep={step}
          title="Choose Your Platform"
          description="Select where you manage your notes"
        >
          <div className="grid sm:grid-cols-2 gap-4">
            {[
              { id: 'obsidian', label: 'Obsidian', desc: 'Recommended - Full feature support' },
              { id: 'logseq', label: 'Logseq', desc: 'Outliner-based notes' },
              { id: 'markdown', label: 'Plain Markdown', desc: 'Any markdown editor' },
              { id: 'custom', label: 'Custom', desc: 'Other platforms' },
            ].map((platform) => (
              <button
                key={platform.id}
                onClick={() => updateState({ platform: platform.id as WizardState['platform'] })}
                className={`p-4 rounded-lg border-2 text-left transition-all ${
                  state.platform === platform.id
                    ? 'border-accent bg-accent/10'
                    : 'border-border hover:border-accent/50'
                }`}
              >
                <div className="font-semibold text-text-primary mb-1">{platform.label}</div>
                <div className="text-sm text-text-secondary">{platform.desc}</div>
              </button>
            ))}
          </div>
        </WizardStep>

        {/* Step 2: AI Provider */}
        <WizardStep
          stepNumber={2}
          currentStep={step}
          title="Select AI Provider"
          description="Choose how you want to process your notes"
        >
          <div className="grid sm:grid-cols-2 gap-4">
            {[
              { id: 'ollama', label: 'Ollama', desc: 'Local, private, free', badge: 'Privacy' },
              { id: 'openai', label: 'OpenAI', desc: 'GPT-4, easiest setup', badge: 'Popular' },
              { id: 'anthropic', label: 'Anthropic', desc: 'Claude 3.5 Sonnet', badge: 'Quality' },
              { id: 'vertex', label: 'Vertex AI', desc: 'Google Gemini', badge: 'Enterprise' },
            ].map((provider) => (
              <button
                key={provider.id}
                onClick={() => updateState({ aiProvider: provider.id as WizardState['aiProvider'] })}
                className={`p-4 rounded-lg border-2 text-left transition-all ${
                  state.aiProvider === provider.id
                    ? 'border-accent bg-accent/10'
                    : 'border-border hover:border-accent/50'
                }`}
              >
                <div className="flex items-start justify-between mb-1">
                  <div className="font-semibold text-text-primary">{provider.label}</div>
                  <span className="text-xs px-2 py-1 rounded-full bg-accent/20 text-accent">
                    {provider.badge}
                  </span>
                </div>
                <div className="text-sm text-text-secondary">{provider.desc}</div>
              </button>
            ))}
          </div>
        </WizardStep>

        {/* Step 3: Modules */}
        <WizardStep
          stepNumber={3}
          currentStep={step}
          title="Select Modules"
          description="Choose which features you want to enable"
        >
          <div className="space-y-3">
            {[
              {
                id: 'foundation',
                label: 'Foundation',
                desc: 'Basic setup and configuration',
                required: true,
              },
              {
                id: 'meetingProcessing',
                label: 'Meeting Processing',
                desc: 'AI-powered summaries and action items',
              },
              {
                id: 'ragSearch',
                label: 'RAG Search',
                desc: 'Semantic search across your knowledge base',
              },
              {
                id: 'calendar',
                label: 'Calendar Integration',
                desc: 'Proactive meeting briefs',
              },
              {
                id: 'automation',
                label: 'Automation',
                desc: 'Hands-free processing with n8n',
              },
            ].map((module) => (
              <label
                key={module.id}
                className={`flex items-start gap-3 p-4 rounded-lg border-2 cursor-pointer transition-all ${
                  state.modules[module.id as keyof typeof state.modules]
                    ? 'border-accent bg-accent/10'
                    : 'border-border hover:border-accent/50'
                } ${module.required ? 'opacity-75 cursor-not-allowed' : ''}`}
              >
                <input
                  type="checkbox"
                  checked={state.modules[module.id as keyof typeof state.modules]}
                  disabled={module.required}
                  onChange={(e) =>
                    updateState({
                      modules: {
                        ...state.modules,
                        [module.id]: e.target.checked,
                      },
                    })
                  }
                  className="mt-1 w-5 h-5 rounded border-border bg-surface text-accent focus:ring-accent focus:ring-offset-0"
                />
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-text-primary">{module.label}</span>
                    {module.required && (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-accent/20 text-accent">
                        Required
                      </span>
                    )}
                  </div>
                  <div className="text-sm text-text-secondary mt-1">{module.desc}</div>
                </div>
              </label>
            ))}
          </div>
        </WizardStep>

        {/* Step 4: Preferences */}
        <WizardStep
          stepNumber={4}
          currentStep={step}
          title="Configure Preferences"
          description="Customize your setup"
        >
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-text-primary mb-2">
                Vault Path
              </label>
              <input
                type="text"
                value={state.preferences.vaultPath}
                onChange={(e) =>
                  updateState({
                    preferences: { ...state.preferences, vaultPath: e.target.value },
                  })
                }
                className="w-full px-4 py-2 bg-surface border border-border rounded-lg text-text-primary focus:outline-none focus:border-accent"
                placeholder="~/Documents/MyVault"
              />
            </div>

            <div className="grid sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-text-primary mb-2">
                  Meetings Folder
                </label>
                <input
                  type="text"
                  value={state.preferences.meetingsFolder}
                  onChange={(e) =>
                    updateState({
                      preferences: { ...state.preferences, meetingsFolder: e.target.value },
                    })
                  }
                  className="w-full px-4 py-2 bg-surface border border-border rounded-lg text-text-primary focus:outline-none focus:border-accent"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-text-primary mb-2">
                  Transcripts Folder
                </label>
                <input
                  type="text"
                  value={state.preferences.transcriptsFolder}
                  onChange={(e) =>
                    updateState({
                      preferences: { ...state.preferences, transcriptsFolder: e.target.value },
                    })
                  }
                  className="w-full px-4 py-2 bg-surface border border-border rounded-lg text-text-primary focus:outline-none focus:border-accent"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-text-primary mb-2">
                Summary Style
              </label>
              <div className="flex gap-3">
                {['concise', 'detailed'].map((style) => (
                  <button
                    key={style}
                    onClick={() =>
                      updateState({
                        preferences: {
                          ...state.preferences,
                          summaryStyle: style as 'concise' | 'detailed',
                        },
                      })
                    }
                    className={`flex-1 px-4 py-2 rounded-lg border-2 transition-all ${
                      state.preferences.summaryStyle === style
                        ? 'border-accent bg-accent/10 text-accent'
                        : 'border-border text-text-secondary hover:border-accent/50'
                    }`}
                  >
                    {style.charAt(0).toUpperCase() + style.slice(1)}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-text-primary mb-2">
                Action Item Format
              </label>
              <input
                type="text"
                value={state.preferences.actionItemFormat}
                onChange={(e) =>
                  updateState({
                    preferences: { ...state.preferences, actionItemFormat: e.target.value },
                  })
                }
                className="w-full px-4 py-2 bg-surface border border-border rounded-lg text-text-primary font-mono text-sm focus:outline-none focus:border-accent"
              />
            </div>
          </div>
        </WizardStep>

        {/* Step 5: Generate */}
        <WizardStep
          stepNumber={5}
          currentStep={step}
          title="Generate Configuration"
          description="Review and download your configuration"
        >
          <div className="space-y-6">
            {/* Summary */}
            <div className="p-4 bg-surface rounded-lg border border-border">
              <h3 className="font-semibold text-text-primary mb-3">Configuration Summary</h3>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-text-secondary">Platform:</span>
                  <span className="text-text-primary font-medium capitalize">{state.platform}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-secondary">AI Provider:</span>
                  <span className="text-text-primary font-medium capitalize">
                    {state.aiProvider}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-secondary">Modules:</span>
                  <span className="text-text-primary font-medium">
                    {Object.values(state.modules).filter(Boolean).length} enabled
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-secondary">Vault:</span>
                  <span className="text-text-primary font-medium">
                    {state.preferences.vaultPath}
                  </span>
                </div>
              </div>
            </div>

            {/* Preview */}
            <div>
              <h3 className="font-semibold text-text-primary mb-3">Config Preview</h3>
              <pre className="code-block text-xs max-h-64 overflow-y-auto">
                {generateConfigYAML()}
              </pre>
            </div>

            {/* Download button */}
            <button
              onClick={downloadZip}
              disabled={isGenerating}
              className="btn-primary w-full text-lg py-4"
            >
              {isGenerating ? (
                <>
                  <svg
                    className="animate-spin -ml-1 mr-3 h-5 w-5 text-white inline"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    />
                  </svg>
                  Generating...
                </>
              ) : (
                <>
                  Download Configuration
                  <svg
                    className="w-5 h-5 ml-2 inline"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                    />
                  </svg>
                </>
              )}
            </button>

            <button
              onClick={() => resetWizard()}
              className="btn-secondary w-full"
            >
              Start Over
            </button>
          </div>
        </WizardStep>

        {/* Navigation */}
        {step < 5 && (
          <div className="flex items-center justify-between pt-6 border-t border-border mt-8">
            <button
              onClick={prevStep}
              disabled={step === 1}
              className="btn-secondary disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <svg
                className="w-5 h-5 mr-2 inline"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M15 19l-7-7 7-7"
                />
              </svg>
              Back
            </button>

            <button
              onClick={nextStep}
              disabled={!canProceed()}
              className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {step === 4 ? 'Review' : 'Continue'}
              <svg
                className="w-5 h-5 ml-2 inline"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 5l7 7-7 7"
                />
              </svg>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
