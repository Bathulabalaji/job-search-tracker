import * as DocumentPicker from "expo-document-picker";
import * as WebBrowser from "expo-web-browser";
import { useState } from "react";
import { ActivityIndicator, View } from "react-native";

import { ApiError, retryMessage } from "@/api/client";
import {
  getResumeDocumentUrl,
  useDeleteResumeDocument,
  useReindexResume,
  useUploadResumeDocument,
} from "@/api/resumes";
import type { Resume, ResumeDocument } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Text } from "@/components/ui/text";
import { toast } from "@/lib/toast-bus";
import { useTheme } from "@/theme/theme";
import { radius, space } from "@/theme/tokens";

const MAX_MB = 5;

function describe(error: unknown): string {
  if (error instanceof ApiError)
    return error.status === 429 ? retryMessage(error) : error.message;
  return "Something went wrong.";
}

export function statusOf(doc: ResumeDocument): {
  label: string;
  tone: "success" | "muted" | "danger";
} {
  if (doc.text_status === "failed" || doc.embed_status === "failed")
    return { label: "Failed", tone: "danger" };
  if (doc.embed_status === "ready")
    return { label: "Indexed", tone: "success" };
  if (doc.processing_error) return { label: "Indexing paused", tone: "muted" };
  return { label: "Indexing…", tone: "muted" };
}

/** The PDF attached to a resume: pick one, see indexing progress, open or remove it. */
export function ResumeFile({ resume }: { resume: Resume }) {
  const { colors } = useTheme();
  const uploadDoc = useUploadResumeDocument();
  const removeDoc = useDeleteResumeDocument();
  const reindex = useReindexResume();
  const [opening, setOpening] = useState(false);
  const doc = resume.document;
  const busy = uploadDoc.isPending || removeDoc.isPending || reindex.isPending;

  const pick = async () => {
    const result = await DocumentPicker.getDocumentAsync({
      type: "application/pdf",
      copyToCacheDirectory: true,
      multiple: false,
    });
    if (result.canceled || !result.assets[0]) return;
    const asset = result.assets[0];
    if ((asset.size ?? 0) > MAX_MB * 1024 * 1024) {
      toast.error(`That file is over ${MAX_MB} MB.`);
      return;
    }
    uploadDoc.mutate(
      {
        id: resume.id,
        file: {
          uri: asset.uri,
          name: asset.name,
          type: asset.mimeType ?? "application/pdf",
        },
      },
      {
        onSuccess: () =>
          toast.success("Resume uploaded", "Indexing in the background."),
        onError: (e) => toast.error("Could not upload", describe(e)),
      },
    );
  };
  const open = async () => {
    setOpening(true);
    try {
      const { url } = await getResumeDocumentUrl(resume.id);
      await WebBrowser.openBrowserAsync(url);
    } catch (e) {
      toast.error("Could not open the file", describe(e));
    } finally {
      setOpening(false);
    }
  };

  return (
    <View
      style={{
        gap: space.sm,
        padding: space.md,
        borderRadius: radius.md,
        borderWidth: 1,
        borderColor: colors.border,
        backgroundColor: colors.surfaceRaised,
      }}
    >
      <Text variant="small" tone="muted">
        PDF file
      </Text>
      {doc ? (
        <>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
            <Icon name="document-text-outline" size={18} color="primary" />
            <Text style={{ flex: 1 }} numberOfLines={1}>
              {doc.file_name}
            </Text>
            {statusOf(doc).tone === "muted" && !doc.processing_error ? (
              <ActivityIndicator size="small" />
            ) : null}
            <Text variant="caption" tone={statusOf(doc).tone}>
              {statusOf(doc).label}
            </Text>
          </View>
          {doc.processing_error ? (
            <Text variant="caption" tone="muted">
              {doc.processing_error}
            </Text>
          ) : null}
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
            <Button
              label="Open"
              icon="open-outline"
              variant="secondary"
              size="sm"
              loading={opening}
              onPress={() => void open()}
            />
            <Button
              label="Replace"
              icon="cloud-upload-outline"
              variant="secondary"
              size="sm"
              disabled={busy}
              onPress={() => void pick()}
            />
            {statusOf(doc).tone !== "success" ? (
              <Button
                label="Retry"
                icon="refresh"
                variant="secondary"
                size="sm"
                loading={reindex.isPending}
                onPress={() =>
                  reindex.mutate(resume.id, {
                    onError: (e) =>
                      toast.error("Could not re-index", describe(e)),
                  })
                }
              />
            ) : null}
            <Button
              label="Remove"
              icon="trash-outline"
              variant="danger"
              size="sm"
              loading={removeDoc.isPending}
              onPress={() =>
                removeDoc.mutate(resume.id, {
                  onSuccess: () => toast.success("File removed"),
                })
              }
            />
          </View>
        </>
      ) : (
        <Button
          label="Upload PDF"
          icon="cloud-upload-outline"
          variant="secondary"
          loading={uploadDoc.isPending}
          onPress={() => void pick()}
        />
      )}
    </View>
  );
}
