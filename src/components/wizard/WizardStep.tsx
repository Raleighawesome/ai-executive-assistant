import React from 'react';

interface WizardStepProps {
  stepNumber: number;
  currentStep: number;
  title: string;
  description: string;
  children: React.ReactNode;
}

export function WizardStep({
  stepNumber,
  currentStep,
  title,
  description,
  children,
}: WizardStepProps) {
  const isActive = stepNumber === currentStep;
  const isCompleted = stepNumber < currentStep;

  if (!isActive) return null;

  return (
    <div className="space-y-6">
      {/* Step indicator */}
      <div className="flex items-center gap-4 pb-6 border-b border-border">
        <div
          className={`flex items-center justify-center w-12 h-12 rounded-full font-bold text-lg ${
            isCompleted
              ? 'bg-accent text-white'
              : isActive
              ? 'bg-accent/20 text-accent border-2 border-accent'
              : 'bg-surface-elevated text-text-muted'
          }`}
        >
          {isCompleted ? '✓' : stepNumber}
        </div>
        <div>
          <h2 className="text-2xl font-bold text-text-primary">{title}</h2>
          <p className="text-text-secondary">{description}</p>
        </div>
      </div>

      {/* Step content */}
      <div className="py-4">{children}</div>
    </div>
  );
}
