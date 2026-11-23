import { useState } from 'react';
import { Button } from '@/components/commons/Button';
import { PosePlaceholder } from '@/components/commons/PosePlaceholder';
import { SkiIcon } from '@/components/commons/icon/SkiIcon';
import { Typography } from '@/components/commons/Typography';
import { ResetType } from 'solarxr-protocol';
import { ResetButton } from '@/components/home/ResetButton';
import { useBreakpoint } from '@/hooks/breakpoint';
import { VerticalStepComponentProps } from '@/components/commons/VerticalStepper';
import { BaseModal } from '@/components/commons/BaseModal';
import { ManualMountingPageStayAligned } from '@/components/onboarding/pages/mounting/ManualMounting';
export function VerifyMountingStep({
  nextStep,
  prevStep,
  isActive,
}: VerticalStepComponentProps) {
  const { isMobile } = useBreakpoint('mobile');
  const [isOpen, setOpen] = useState(false);
  const [disableMounting, setDisableMounting] = useState(false);

  const goNextStep = () => {
    setDisableMounting(false);
    setOpen(false);
    nextStep();
  };

  return (
    <div className="flex flex-col flex-grow justify-between py-2 gap-2">
      <div className="flex flex-col flex-grow">
        <div className="flex flex-grow flex-col gap-4 max-w-sm">
          <div className="flex flex-col gap-2">
            <Typography id="onboarding-automatic_mounting-mounting_reset-step-0" />
            <Typography id="onboarding-automatic_mounting-mounting_reset-step-1" />
          </div>
        </div>

        {isMobile && (
          // TODO(art): replace placeholder pose illustration
          <div className="flex flex-col items-center justify-center py-4">
            <PosePlaceholder
              icon={<SkiIcon size={72} />}
              labelId="onboarding-automatic_mounting-mounting_reset-title"
              className="w-full max-w-sm min-h-[200px]"
            />
          </div>
        )}

        {!isMobile && (
          // TODO(art): replace placeholder pose illustration
          <div className="flex flex-col py-4 items-center justify-center">
            <PosePlaceholder
              icon={<SkiIcon size={96} />}
              labelId="onboarding-automatic_mounting-mounting_reset-title"
              className="w-80 min-h-[240px]"
            />
          </div>
        )}
        <div className="flex gap-3 justify-between">
          <Button
            variant={'secondary'}
            onClick={prevStep}
            id="onboarding-automatic_mounting-prev_step"
          />
          <Button
            disabled={disableMounting}
            variant={'secondary'}
            className="self-start mt-auto"
            onClick={() => setOpen(true)}
            id="onboarding-automatic_mounting-manual_mounting"
          />
          <BaseModal isOpen={isOpen} onRequestClose={() => setOpen(false)}>
            <ManualMountingPageStayAligned>
              <div className="flex flex-row gap-3 mt-auto">
                <Button
                  variant="primary"
                  onClick={goNextStep}
                  id="onboarding-stay_aligned-manual_mounting-done"
                />
              </div>
            </ManualMountingPageStayAligned>
          </BaseModal>

          <ResetButton
            onClick={() => setDisableMounting(true)}
            type={ResetType.Mounting}
            group="default"
            onReseted={() => {
              if (isActive) {
                nextStep();
              }
            }}
            onFailed={() => setDisableMounting(false)}
          />
        </div>
      </div>
    </div>
  );
}
