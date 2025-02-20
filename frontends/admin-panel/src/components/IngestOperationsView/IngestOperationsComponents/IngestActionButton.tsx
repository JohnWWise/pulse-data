// Recidiviz - a data platform for criminal justice reform
// Copyright (C) 2022 Recidiviz, Inc.
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program.  If not, see <https://www.gnu.org/licenses/>.
// =============================================================================
import { Button, message } from "antd";
import { useState } from "react";
import {
  exportDatabaseToGCS,
  startIngestRerun,
  triggerTaskScheduler,
  updateIngestQueuesState,
} from "../../../AdminPanelAPI";
import { startRawDataReimport } from "../../../AdminPanelAPI/IngestOperations";
import ActionRegionConfirmationForm, {
  RegionAction,
  RegionActionContext,
  StartIngestRerunContext,
  regionActionNames,
} from "../../Utilities/ActionRegionConfirmationForm";
import { DirectIngestInstance, QueueState } from "../constants";

interface IngestActionButtonProps {
  action: RegionAction;
  stateCode: string;
  instance?: DirectIngestInstance;
  buttonText?: string;
  block?: boolean;
  style?: React.CSSProperties;
  type?: "link" | "text" | "primary" | "default" | "ghost" | "dashed";
  onActionLoadingStateChanged?: (loading: boolean) => void;
  onActionConfirmed?: () => void;
}

const IngestActionButton: React.FC<IngestActionButtonProps> = ({
  action,
  stateCode,
  instance,
  buttonText,
  block,
  style,
  type,
  onActionLoadingStateChanged,
  onActionConfirmed,
}) => {
  const [isConfirmationModalVisible, setIsConfirmationModalVisible] =
    useState(false);

  const setActionLoadingState = (loading: boolean) => {
    if (onActionLoadingStateChanged) {
      onActionLoadingStateChanged(loading);
    }
  };

  const setActionConfirmed = () => {
    if (onActionConfirmed) {
      onActionConfirmed();
    }
  };

  const onIngestActionConfirmation = async (context: RegionActionContext) => {
    setIsConfirmationModalVisible(false);

    setActionLoadingState(true);
    const unsupportedIngestAction = "Unsupported ingest action";
    switch (context.ingestAction) {
      case RegionAction.TriggerTaskScheduler:
        if (instance) {
          await triggerTaskScheduler(stateCode, instance);
          setActionConfirmed();
        }
        break;
      case RegionAction.PauseIngestQueues:
        await updateIngestQueuesState(stateCode, QueueState.PAUSED);
        setActionConfirmed();
        break;
      case RegionAction.ResumeIngestQueues:
        await updateIngestQueuesState(stateCode, QueueState.RUNNING);
        setActionConfirmed();
        break;

      // TODO(#24652): delete after dataflow is fully enabled
      case RegionAction.StartIngestRerun:
        if (instance === undefined) {
          throw new Error(
            "Must have a defined instance before starting an ingest rerun."
          );
        }
        if (context.ingestAction !== RegionAction.StartIngestRerun) {
          throw new Error(
            "Context for ingest rerun must be of type StartIngestRerunContext."
          );
        }
        if (
          (context as StartIngestRerunContext)
            .ingestRerunRawDataSourceInstance === undefined
        ) {
          throw new Error(
            "Context for ingest rerun must have a defined ingestRerunRawDataSourceInstance."
          );
        } else {
          const res = await startIngestRerun(
            stateCode,
            instance,
            (context as StartIngestRerunContext)
              .ingestRerunRawDataSourceInstance
          );
          if (res.status === 200) {
            message.success(`Start Ingest Rerun Succeeded!`, 7);
          } else {
            const text = await res.text();
            message.error(`Start Ingest Rerun Failed: ${text}`, 7);
          }
        }
        setActionConfirmed();
        break;
      case RegionAction.StartRawDataReimport:
        if (context.ingestAction !== RegionAction.StartRawDataReimport) {
          throw new Error(
            "Context for raw data reimport must be of type StartRawDataReimport."
          );
        } else {
          const res = await startRawDataReimport(stateCode);
          if (res.status === 200) {
            message.success(`Start Raw Data Reimport Succeeded!`, 7);
          } else {
            const text = await res.text();
            message.error(`Start Raw Data Reimport Failed: ${text}`, 7);
          }
        }
        setActionConfirmed();
        break;
      case RegionAction.ExportToGCS:
        if (instance) {
          message.info("Exporting database...");
          const r = await exportDatabaseToGCS(stateCode, instance);
          if (r.status >= 400) {
            const text = await r.text();
            message.error(`Export to GCS failed: ${text}`);
          } else {
            message.success("GCS Export succeeded!");
          }
          setActionConfirmed();
        }
        break;
      default:
        throw unsupportedIngestAction;
    }
    setActionLoadingState(false);
  };

  return (
    <>
      <Button
        style={style}
        block={block}
        type={type}
        onClick={() => {
          setIsConfirmationModalVisible(true);
        }}
        key={action}
      >
        {buttonText}
      </Button>
      <ActionRegionConfirmationForm
        visible={isConfirmationModalVisible}
        onConfirm={onIngestActionConfirmation}
        onCancel={() => {
          setIsConfirmationModalVisible(false);
        }}
        action={action}
        actionName={regionActionNames[action]}
        regionCode={stateCode}
        ingestInstance={instance}
      />
    </>
  );
};

export default IngestActionButton;
