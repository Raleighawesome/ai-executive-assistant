import { atom } from 'nanostores';
import { persistentAtom } from '@nanostores/persistent';

export interface WizardState {
  platform: 'obsidian' | 'logseq' | 'markdown' | 'custom' | null;
  aiProvider: 'openai' | 'vertex' | 'anthropic' | 'ollama' | 'custom' | null;
  modules: {
    foundation: boolean;
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

export const defaultState: WizardState = {
  platform: null,
  aiProvider: null,
  modules: {
    foundation: true, // Required
    meetingProcessing: false,
    ragSearch: false,
    calendar: false,
    automation: false,
  },
  preferences: {
    vaultPath: '~/Documents/MyVault',
    meetingsFolder: 'Meetings',
    transcriptsFolder: 'Transcripts',
    peopleFolder: 'People',
    templatesFolder: 'Templates',
    summaryStyle: 'concise',
    actionItemFormat: '- [ ] @Owner — Task',
  },
};

// Persistent store that saves to localStorage
export const wizardState = persistentAtom<WizardState>(
  'ai-assistant-wizard',
  defaultState,
  {
    encode: JSON.stringify,
    decode: JSON.parse,
  }
);

// Current step tracking
export const currentStep = atom<number>(1);

// Reset function
export function resetWizard() {
  wizardState.set(defaultState);
  currentStep.set(1);
}
