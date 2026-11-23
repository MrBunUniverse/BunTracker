import { useOnboarding } from '@/hooks/onboarding';
import { Typography } from '@/components/commons/Typography';
import { Button } from '@/components/commons/Button';
import { useAtomValue } from 'jotai';
import { serverGuardsAtom } from '@/store/app-store';
import { useWebsocketAPI } from '@/hooks/websocket-api';
import { useEffect, useState } from 'react';
import {
  CancelUserHeightCalibrationT,
  ChangeSettingsRequestT,
  ModelSettingsT,
  ResetType,
  RpcMessage,
  SkeletonConfigRequestT,
  SkeletonConfigResponseT,
  SkeletonHeightT,
  SkeletonResetAllRequestT,
  StartUserHeightCalibrationT,
  UserHeightCalibrationStatus,
  UserHeightRecordingStatusResponseT,
} from 'solarxr-protocol';
import { HeightSelectionInput } from './HeightInput';
import { Tooltip } from '@/components/commons/Tooltip';
import classNames from 'classnames';
import { SkeletonVisualizerWidget } from '@/components/widgets/SkeletonVisualizerWidget';
import { CheckIcon } from '@/components/commons/icon/CheckIcon';
import { ControllerIcon } from '@/components/commons/icon/ControllerIcon';
import { HeadsetIcon } from '@/components/commons/icon/HeadsetIcon';
import { HumanIcon } from '@/components/commons/icon/HumanIcon';
import { WarningIcon } from '@/components/commons/icon/WarningIcon';
import { PosePlaceholder } from '@/components/commons/PosePlaceholder';
import { useDebouncedEffect } from '@/hooks/timeout';
import { restartAndPlay, scaledProportionsClick } from '@/sounds/sounds';
import { CrossIcon } from '@/components/commons/icon/CrossIcon';
import { TipBox } from '@/components/commons/TipBox';
import { Localized } from '@fluent/react';
import { ResetButton } from '@/components/home/ResetButton';
import { ProgressBar } from '@/components/commons/ProgressBar';
import { useBreakpoint } from '@/hooks/breakpoint';
import { useConfig } from '@/hooks/config';
import { ProportionsResetModal } from './ProportionsResetModal';

const statusSteps = [
  // Order matters be carefull
  UserHeightCalibrationStatus.NONE,
  UserHeightCalibrationStatus.RECORDING_FLOOR,
  UserHeightCalibrationStatus.WAITING_FOR_CONTROLLER_PITCH,
  UserHeightCalibrationStatus.WAITING_FOR_RISE,
  UserHeightCalibrationStatus.WAITING_FOR_FW_LOOK,
  UserHeightCalibrationStatus.RECORDING_HEIGHT,
  UserHeightCalibrationStatus.DONE,
];

const progressSteps: UserHeightCalibrationStatus[] = statusSteps.filter(
  (s) => s !== UserHeightCalibrationStatus.NONE
);

const errorSteps = [
  UserHeightCalibrationStatus.ERROR_TIMEOUT,
  UserHeightCalibrationStatus.ERROR_TOO_HIGH,
  UserHeightCalibrationStatus.ERROR_TOO_SMALL,
];

// TODO(art): replace placeholder pose illustration
function renderStatusPoseIcon(status: UserHeightCalibrationStatus) {
  switch (status) {
    case UserHeightCalibrationStatus.DONE:
      return <CheckIcon size={32} className="fill-status-success" />;
    case UserHeightCalibrationStatus.RECORDING_FLOOR:
      return <ControllerIcon width={44} />;
    case UserHeightCalibrationStatus.WAITING_FOR_RISE:
    case UserHeightCalibrationStatus.RECORDING_HEIGHT:
      return <HumanIcon width={44} />;
    case UserHeightCalibrationStatus.ERROR_TIMEOUT:
    case UserHeightCalibrationStatus.ERROR_TOO_HIGH:
    case UserHeightCalibrationStatus.ERROR_TOO_SMALL:
      return <WarningIcon width={36} className="text-status-critical" />;
    default:
      return null;
  }
}

function Stepper({ status }: { status: UserHeightRecordingStatusResponseT }) {
  const stepIndex = progressSteps.indexOf(status.status);
  const isError = errorSteps.includes(status.status);
  const progress = isError ? 1 : (stepIndex + 1) / progressSteps.length;

  const { isXs } = useBreakpoint('xs');

  return (
    <div className="flex flex-col gap-2 px-2">
      <div className="flex gap-2 items-center">
        <div
          className={classNames(
            'w-8 aspect-square rounded-full fill-background-10 flex items-center justify-center',
            {
              'bg-background-70':
                status.status !== UserHeightCalibrationStatus.DONE && !isError,
              'bg-accent-background-10':
                status.status === UserHeightCalibrationStatus.DONE,
              'bg-status-critical': isError,
            }
          )}
        >
          {status.status !== UserHeightCalibrationStatus.DONE && !isError && (
            <Typography variant={isXs ? 'section-title' : 'standard'}>
              {stepIndex + 1}
            </Typography>
          )}
          {status.status === UserHeightCalibrationStatus.DONE && (
            <CheckIcon size={12} />
          )}
          {isError && <CrossIcon />}
        </div>
        <Typography
          id={`onboarding-user_height-calibration-${UserHeightCalibrationStatus[status.status]}`}
          variant={isXs ? 'section-title' : 'standard'}
        />
      </div>
      <ProgressBar
        progress={progress}
        animated
        colorClass={
          status.status === UserHeightCalibrationStatus.DONE
            ? 'bg-status-success'
            : isError
              ? 'bg-status-critical'
              : undefined
        }
      />
    </div>
  );
}

function UserHeightStatus({
  status,
}: {
  status: UserHeightRecordingStatusResponseT;
}) {
  const { isXs } = useBreakpoint('xs');

  return (
    <div className="flex flex-col h-full rounded-t-lg xs:rounded-b-lg bg-background-60 xs:py-2 px-2 pt-4 relative">
      <div className="flex flex-col bg-background-60 rounded-lg">
        <div className="px-4 hidden xs:block">
          <Typography
            variant="mobile-title"
            id="onboarding-user_height-calibration-title"
          />
        </div>
        <div className="flex flex-col py-2">
          <Stepper status={status} />
        </div>
      </div>

      <div className="flex flex-grow justify-center h-full min-h-0 items-center">
        {renderStatusPoseIcon(status.status) && (
          // TODO(art): replace placeholder pose illustration
          <div className="h-full w-full flex justify-center items-center p-2 max-h-[950px]">
            <PosePlaceholder
              icon={renderStatusPoseIcon(status.status)}
              labelId={`onboarding-user_height-calibration-${UserHeightCalibrationStatus[status.status]}`}
              className="h-full w-full max-w-md"
            />
          </div>
        )}
        {status.status === UserHeightCalibrationStatus.WAITING_FOR_FW_LOOK && (
          // TODO(art): replace placeholder pose illustration
          <div className="h-full w-full flex p-2">
            <div className="grid grid-rows-3 h-full w-full gap-1 xs:gap-3 max-h-[950px]">
              <div className="bg-background-70 border border-[var(--material-border-subtle)] rounded-md flex gap-4 items-center px-4 relative">
                <CheckIcon className="sm:w-6 w-4 h-auto shrink-0 fill-status-success" />
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border border-[var(--material-border-primary)] bg-background-60/60 text-background-20">
                  <HeadsetIcon width={26} />
                </div>
                <Typography
                  variant={isXs ? 'section-title' : 'standard'}
                  whitespace="whitespace-pre-wrap"
                  id="onboarding-user_height-calibration-WAITING_FOR_FW_LOOK-ok"
                />
              </div>
              <div className="bg-background-70 border border-[var(--material-border-subtle)] rounded-md flex gap-4 items-center px-4 relative">
                <CrossIcon className="sm:w-6 w-5 h-auto shrink-0 fill-status-critical" />
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border border-[var(--material-border-primary)] bg-background-60/60 text-background-20">
                  <span className="inline-flex rotate-[24deg]">
                    <HeadsetIcon width={26} />
                  </span>
                </div>
                <Typography
                  variant={isXs ? 'section-title' : 'standard'}
                  whitespace="whitespace-pre-wrap"
                  id="onboarding-user_height-calibration-WAITING_FOR_FW_LOOK-low"
                />
              </div>
              <div className="bg-background-70 border border-[var(--material-border-subtle)] rounded-md flex gap-4 items-center px-4 relative">
                <CrossIcon className="sm:w-6 w-5 h-auto shrink-0 fill-status-critical" />
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border border-[var(--material-border-primary)] bg-background-60/60 text-background-20">
                  <span className="inline-flex -rotate-[24deg]">
                    <HeadsetIcon width={26} />
                  </span>
                </div>
                <Typography
                  variant={isXs ? 'section-title' : 'standard'}
                  whitespace="whitespace-pre-wrap"
                  id="onboarding-user_height-calibration-WAITING_FOR_FW_LOOK-high"
                />
              </div>
            </div>
          </div>
        )}
        {status.status ===
          UserHeightCalibrationStatus.WAITING_FOR_CONTROLLER_PITCH && (
          // TODO(art): replace placeholder pose illustration
          <div className="h-full w-full flex p-2">
            <div className="grid grid-cols-3 h-full w-full gap-3 max-h-[950px]">
              <div className="bg-background-70 border border-[var(--material-border-primary)] rounded-md flex flex-col gap-2 justify-center items-center p-3 relative overflow-clip">
                <CheckIcon className="sm:w-6 w-4 h-auto absolute top-2 left-2 fill-status-success" />
                <div className="fill-background-20 text-background-20 rotate-[180deg]">
                  <ControllerIcon width={36} />
                </div>
              </div>
              <div className="bg-background-70 border border-[var(--material-border-primary)] rounded-md flex flex-col gap-2 justify-center items-center p-3 relative overflow-clip">
                <CrossIcon className="sm:w-7 w-5 h-auto absolute top-2 left-2 fill-status-critical" />
                <div className="fill-background-20 text-background-20 rotate-[90deg]">
                  <ControllerIcon width={36} />
                </div>
              </div>
              <div className="bg-background-70 border border-[var(--material-border-primary)] rounded-md flex flex-col gap-2 justify-center items-center p-3 relative overflow-clip">
                <CrossIcon className="sm:w-7 w-5 h-auto absolute top-2 left-2 fill-status-critical" />
                <div className="fill-background-20 text-background-20">
                  <ControllerIcon width={36} />
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export function ScaledProportionsPage() {
  const [hmdHeight, setHmdHeight] = useState(0);
  const [tmpHeight, setTmpHeight] = useState(0);
  const { config, setConfig } = useConfig();
  const { applyProgress, state } = useOnboarding();

  const serverGuards = useAtomValue(serverGuardsAtom);

  const [status, setState] = useState<UserHeightRecordingStatusResponseT>();
  const [auto, setAuto] = useState(false);
  const { sendRPCPacket, useRPCPacket } = useWebsocketAPI();
  const [resetModal, setResetModal] = useState<null | 'manual' | 'auto'>(null);

  applyProgress(0.9);

  const start = () => {
    sendRPCPacket(
      RpcMessage.StartUserHeightCalibration,
      new StartUserHeightCalibrationT()
    );
  };

  const cancel = () => {
    sendRPCPacket(
      RpcMessage.CancelUserHeightCalibration,
      new CancelUserHeightCalibrationT()
    );
  };

  // Makes it so you dont get spammed by sounds if multiple status complete at once
  useDebouncedEffect(
    () => {
      if (!config || !config.feedbackSound) return;
      if (
        !status ||
        errorSteps.includes(status.status) ||
        status.status == UserHeightCalibrationStatus.NONE ||
        status.status == UserHeightCalibrationStatus.WAITING_FOR_FW_LOOK ||
        status.status ==
          UserHeightCalibrationStatus.WAITING_FOR_CONTROLLER_PITCH
      )
        return;
      restartAndPlay(scaledProportionsClick, config.feedbackSoundVolume);
    },
    [status?.status],
    300
  );

  const applyHeight = (newHeight: number) => {
    setHmdHeight(newHeight);
    const settingsRequest = new ChangeSettingsRequestT();
    settingsRequest.modelSettings = new ModelSettingsT(
      null,
      null,
      null,
      new SkeletonHeightT(newHeight, 0)
    );
    sendRPCPacket(RpcMessage.ChangeSettingsRequest, settingsRequest);
    sendRPCPacket(
      RpcMessage.SkeletonResetAllRequest,
      new SkeletonResetAllRequestT()
    );
    setConfig({ lastUsedProportions: 'scaled' });
  };

  useRPCPacket(
    RpcMessage.UserHeightRecordingStatusResponse,
    (res: UserHeightRecordingStatusResponseT) => {
      if (res.status !== UserHeightCalibrationStatus.NONE) {
        setAuto(true);
      }

      setState(res);
      setHmdHeight(res.hmdHeight);

      if (res.status === UserHeightCalibrationStatus.DONE) {
        setConfig({ lastUsedProportions: 'scaled' });
      }
    }
  );

  useRPCPacket(
    RpcMessage.SkeletonConfigResponse,
    (res: SkeletonConfigResponseT) => {
      setHmdHeight(res.userHeight);
    }
  );

  useEffect(() => {
    sendRPCPacket(
      RpcMessage.SkeletonConfigRequest,
      new SkeletonConfigRequestT()
    );

    return () => {
      cancel();
    };
  }, []);

  useEffect(() => {
    const checkNotAuto = (status: UserHeightCalibrationStatus) =>
      status === UserHeightCalibrationStatus.DONE ||
      errorSteps.includes(status);

    if (status && checkNotAuto(status.status)) {
      const id = setTimeout(
        () => {
          if (status && checkNotAuto(status.status)) {
            setAuto(false);
            sendRPCPacket(
              RpcMessage.SkeletonConfigRequest,
              new SkeletonConfigRequestT()
            ); // Re ask the user height so it resets back to the correct value
          }
        },
        status.status === UserHeightCalibrationStatus.DONE ? 2000 : 10_000
      );
      return () => {
        clearTimeout(id);
      };
    }
  }, [status]);

  const acceptHeight = () => {
    if (resetModal === 'manual') {
      applyHeight(tmpHeight);
    } else if (resetModal === 'auto') {
      start();
    }

    setResetModal(null);
  };

  return (
    <div
      className={classNames(
        'flex flex-col gap-2 w-full h-full relative z-10 overflow-y-auto',
        {
          'p-4': !state.alonePage,
          'bg-background-70': state.alonePage,
        }
      )}
    >
      <ProportionsResetModal
        isOpen={resetModal !== null}
        onClose={() => setResetModal(null)}
        accept={acceptHeight}
      />
      {/* The preview spans the page and takes all spare height; the tip, status and controls keep a readable
          width. The widget sizes itself from its parent (h-full), and a flex item's height is indefinite here, so it
          is placed absolutely inside the item. Below the minimum the page scrolls rather than squeezing the canvas. */}
      {/* Stays clear of the wizard's ESC key in the top-right corner (64 px wide with its inset). */}
      {!auto && (
        <div className="shrink-0 w-full max-w-[min(42rem,calc(100%-10rem))] mx-auto p-0 xs:p-2">
          <Localized id="onboarding-user_height-manual-tip">
            <TipBox className="p-2 xs:p-4">PRO TIP</TipBox>
          </Localized>
        </div>
      )}
      <div className="relative flex-1 min-h-[22rem]">
        <div className="absolute inset-0">
          <SkeletonVisualizerWidget />
        </div>
      </div>
      <div
        className={classNames(
          'shrink-0 max-w-2xl w-full mx-auto overflow-hidden transition-[height,opacity] duration-200',
          auto ? 'h-72 opacity-100' : 'h-0 opacity-0'
        )}
      >
        {status && <UserHeightStatus status={status} />}
      </div>

      <div
        className={classNames(
          'shrink-0 max-w-lg w-full mx-auto flex flex-col gap-3 p-4 bg-background-60 rounded-[12px] border border-[var(--material-border-subtle)]'
        )}
      >
        <HeightSelectionInput
          hmdHeight={hmdHeight}
          setHmdHeight={(height) => {
            if (
              config?.lastUsedProportions != null &&
              config.lastUsedProportions !== 'scaled'
            ) {
              setTmpHeight(height);
              setResetModal('manual');
            } else {
              applyHeight(height);
            }
            setAuto(false);
          }}
        />
        <Tooltip
          disabled={serverGuards?.canDoUserHeightCalibration}
          preferedDirection="top"
          content={<Typography id="onboarding-user_height-need_head_tracker" />}
        >
          <Button
            variant="primary"
            className="w-full"
            disabled={!serverGuards?.canDoUserHeightCalibration}
            onClick={() => {
              if (
                config?.lastUsedProportions != null &&
                config.lastUsedProportions !== 'scaled'
              ) {
                setResetModal('auto');
              } else {
                start();
              }
            }}
            id="onboarding-user_height-calculate"
          />
        </Tooltip>
        <div className="w-full grid grid-cols-2 items-center gap-2">
          {state.alonePage && (
            <>
              <Button
                variant="tertiary"
                className="w-full"
                id="onboarding-user_height-manual-proportions"
                to="/onboarding/body-proportions/manual"
                state={{ alonePage: state.alonePage }}
              />
              <ResetButton
                type={ResetType.Full}
                className="w-full bg-background-50 hover:bg-background-40 text-background-10"
              />
            </>
          )}
          {!state.alonePage && (
            <Button
              variant="primary"
              className="col-span-2 w-full"
              id="onboarding-user_height-next_step"
              to="/onboarding/quiz/usage"
            />
          )}
        </div>
      </div>
    </div>
  );
}
