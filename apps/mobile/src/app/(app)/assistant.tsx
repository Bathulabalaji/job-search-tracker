import { Stack } from "expo-router";
import { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  TextInput,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import {
  useChatConfig,
  useConversation,
  useConversations,
  useCreateConversation,
  useDeleteConversation,
  type ChatMessage,
} from "@/api/chat";
import { IconButton } from "@/components/ui/icon-button";
import { Icon } from "@/components/ui/icon";
import { Sheet } from "@/components/ui/sheet";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { Text } from "@/components/ui/text";
import { LiteMarkdown } from "@/features/assistant/lite-markdown";
import {
  errorText,
  useChatStream,
  type LiveTool,
  type TurnError,
} from "@/features/assistant/use-chat-stream";
import { haptics } from "@/lib/haptics";
import { MAX_CONTENT_WIDTH } from "@/components/ui/screen";
import { radius, space } from "@/theme/tokens";
import { useTheme } from "@/theme/theme";

const TOOL_LABELS: Record<string, string> = {
  get_today: "Today's plan",
  get_pipeline_summary: "Pipeline summary",
  list_opportunities: "Opportunities",
  get_opportunity: "Opportunity details",
  list_followups: "Follow-ups",
  get_weekly_analytics: "Weekly analytics",
  list_contacts: "Contacts",
  list_prep_items: "Prep topics",
  list_resumes: "Resumes",
};

type Row =
  | { key: string; kind: "user"; text: string }
  | {
      key: string;
      kind: "assistant";
      text: string;
      tools: { name: string; ok?: boolean | null; summary?: string | null }[];
      status?: ChatMessage["status"];
      streaming?: boolean;
      error?: TurnError | null;
      onRetry?: () => void;
    };

export default function AssistantScreen() {
  const config = useChatConfig();
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  // Bumped only when the user switches chats, so a reply that is streaming is never lost.
  const [panelKey, setPanelKey] = useState(0);

  const select = (id: number | null) => {
    setConversationId(id);
    setPanelKey((k) => k + 1);
    setHistoryOpen(false);
  };

  return (
    <>
      <Stack.Screen
        options={{
          title: "Assistant",
          headerRight: () => (
            <View style={{ flexDirection: "row", gap: 4 }}>
              <IconButton
                icon="time-outline"
                label="Conversations"
                onPress={() => setHistoryOpen(true)}
              />
              <IconButton
                icon="create-outline"
                label="New chat"
                onPress={() => select(null)}
              />
            </View>
          ),
        }}
      />
      {config.isPending ? (
        <Centered>
          <ActivityIndicator />
        </Centered>
      ) : config.isError ? (
        <Centered>
          <ErrorState
            error={config.error}
            onRetry={() => void config.refetch()}
          />
        </Centered>
      ) : !config.data.enabled ? (
        <Centered>
          <EmptyState
            icon="sparkles-outline"
            title="The assistant isn't switched on"
            description="It needs an AI provider key on the server."
          />
        </Centered>
      ) : (
        <ChatPanel
          key={panelKey}
          conversationId={conversationId}
          suggestions={config.data.suggestions}
          maxChars={config.data.max_message_chars}
          onCreated={setConversationId}
        />
      )}
      <HistorySheet
        visible={historyOpen}
        selected={conversationId}
        onClose={() => setHistoryOpen(false)}
        onSelect={select}
      />
    </>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  const { colors } = useTheme();
  return (
    <View
      style={{
        flex: 1,
        justifyContent: "center",
        padding: space.xl,
        backgroundColor: colors.bg,
      }}
    >
      {children}
    </View>
  );
}

function ChatPanel({
  conversationId,
  suggestions,
  maxChars,
  onCreated,
}: {
  conversationId: number | null;
  suggestions: string[];
  maxChars: number;
  onCreated: (id: number) => void;
}) {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const detail = useConversation(conversationId);
  const create = useCreateConversation();
  const { live, send, resume, stop, busy } = useChatStream();
  const [draft, setDraft] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const list = useRef<FlatList<Row>>(null);

  const lastRun = detail.data?.last_run ?? null;
  const persisted = (detail.data?.messages ?? []).filter(
    (m) =>
      !(
        live?.resumingRunId &&
        m.role === "assistant" &&
        m.run_id === live.resumingRunId
      ),
  );

  const retry = async (runId: string) => {
    if (conversationId === null) return;
    setNotice(null);
    const error = await resume(conversationId, runId);
    if (error) setNotice(errorText(error));
  };

  const rows: Row[] = persisted.map((m, index) =>
    m.role === "user"
      ? { key: `m${m.id}`, kind: "user", text: m.content }
      : {
          key: `m${m.id}`,
          kind: "assistant",
          text: m.content,
          tools: m.tool_calls ?? [],
          status: m.status,
          onRetry:
            m.status === "failed" &&
            index === persisted.length - 1 &&
            lastRun?.resumable &&
            lastRun.id === m.run_id &&
            !busy
              ? () => void retry(lastRun.id)
              : undefined,
        },
  );
  if (live?.userText)
    rows.push({ key: "live-user", kind: "user", text: live.userText });
  if (live) {
    rows.push({
      key: "live-reply",
      kind: "assistant",
      text: live.text,
      tools: live.tools,
      streaming: true,
      error: live.error,
      onRetry: live.runId ? () => void retry(live.runId ?? "") : undefined,
    });
  }

  useEffect(() => {
    list.current?.scrollToEnd({ animated: true });
  }, [rows.length, live?.text, live?.tools.length]);

  const submit = async (text: string) => {
    const content = text.trim();
    if (!content || busy) return;
    haptics.tap();
    setDraft("");
    setNotice(null);
    let id = conversationId;
    if (id === null) {
      try {
        id = (await create.mutateAsync()).id;
      } catch (e) {
        setDraft(content);
        setNotice((e as Error).message);
        return;
      }
      onCreated(id);
    }
    const error = await send(id, content);
    if (error) {
      setDraft(content);
      setNotice(errorText(error));
    }
  };

  const empty = rows.length === 0 && !detail.isLoading;
  return (
    <KeyboardAvoidingView
      style={{ flex: 1, backgroundColor: colors.bg }}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      keyboardVerticalOffset={Platform.OS === "ios" ? 90 : 0}
    >
      {empty ? (
        <View
          style={{
            flex: 1,
            justifyContent: "center",
            padding: space.xl,
            gap: space.lg,
            alignItems: "center",
          }}
        >
          <View
            style={{
              width: 56,
              height: 56,
              borderRadius: 28,
              backgroundColor: colors.primarySoft,
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Icon name="sparkles-outline" size={26} color="primary" />
          </View>
          <Text variant="heading" style={{ textAlign: "center" }}>
            Ask about your job search
          </Text>
          <Text tone="muted" style={{ textAlign: "center", maxWidth: 360 }}>
            I can look up your pipeline, follow-ups, interviews, contacts, prep
            and weekly progress. I can't change anything yet.
          </Text>
          <View
            style={{
              flexDirection: "row",
              flexWrap: "wrap",
              gap: space.sm,
              justifyContent: "center",
            }}
          >
            {suggestions.map((s) => (
              <Pressable
                key={s}
                accessibilityRole="button"
                onPress={() => void submit(s)}
                style={({ pressed }) => ({
                  paddingHorizontal: 14,
                  paddingVertical: 8,
                  borderRadius: radius.pill,
                  borderWidth: 1,
                  borderColor: colors.border,
                  backgroundColor: colors.surface,
                  opacity: pressed ? 0.7 : 1,
                })}
              >
                <Text variant="small">{s}</Text>
              </Pressable>
            ))}
          </View>
        </View>
      ) : (
        <FlatList
          ref={list}
          data={rows}
          keyExtractor={(row) => row.key}
          contentContainerStyle={{
            padding: space.lg,
            gap: space.lg,
            width: "100%",
            maxWidth: MAX_CONTENT_WIDTH,
            alignSelf: "center",
          }}
          keyboardDismissMode="interactive"
          keyboardShouldPersistTaps="handled"
          ListHeaderComponent={
            detail.isLoading ? <ActivityIndicator /> : undefined
          }
          renderItem={({ item }) =>
            item.kind === "user" ? (
              <UserBubble text={item.text} />
            ) : (
              <AssistantBubble row={item} />
            )
          }
        />
      )}

      <View
        style={{
          borderTopWidth: 1,
          borderTopColor: colors.border,
          backgroundColor: colors.surface,
          paddingHorizontal: space.md,
          paddingTop: space.sm,
          paddingBottom: Math.max(insets.bottom, space.sm),
        }}
      >
        {notice ? (
          <Text
            variant="small"
            tone="danger"
            accessibilityRole="alert"
            style={{ marginBottom: 6 }}
          >
            {notice}
          </Text>
        ) : null}
        <View
          style={{
            flexDirection: "row",
            alignItems: "flex-end",
            gap: space.sm,
          }}
        >
          <TextInput
            value={draft}
            onChangeText={setDraft}
            placeholder="Ask about your job search…"
            placeholderTextColor={colors.muted}
            multiline
            maxLength={maxChars}
            accessibilityLabel="Message"
            style={{
              flex: 1,
              maxHeight: 120,
              minHeight: 44,
              color: colors.text,
              backgroundColor: colors.bg,
              borderRadius: radius.lg,
              borderWidth: 1,
              borderColor: colors.border,
              paddingHorizontal: 14,
              paddingTop: 11,
              paddingBottom: 11,
              fontSize: 16,
            }}
          />
          {busy ? (
            <IconButton
              icon="stop"
              label="Stop"
              onPress={stop}
              filled
              tone="danger"
            />
          ) : (
            <IconButton
              icon="arrow-up"
              label="Send"
              onPress={() => void submit(draft)}
              filled
              tone="primary"
            />
          )}
        </View>
      </View>
    </KeyboardAvoidingView>
  );
}

function UserBubble({ text }: { text: string }) {
  const { colors } = useTheme();
  return (
    <View style={{ alignItems: "flex-end" }}>
      <View
        style={{
          maxWidth: "85%",
          backgroundColor: colors.primary,
          borderRadius: radius.lg,
          borderBottomRightRadius: 4,
          paddingHorizontal: 14,
          paddingVertical: 10,
        }}
      >
        <Text tone="onPrimary">{text}</Text>
      </View>
    </View>
  );
}

function AssistantBubble({
  row,
}: {
  row: Extract<Row, { kind: "assistant" }>;
}) {
  const { colors } = useTheme();
  const { text, tools, streaming, status, error, onRetry } = row;
  return (
    <View style={{ flexDirection: "row", gap: 10 }}>
      <View
        style={{
          width: 28,
          height: 28,
          borderRadius: 14,
          backgroundColor: colors.primarySoft,
          alignItems: "center",
          justifyContent: "center",
          marginTop: 2,
        }}
      >
        <Icon name="sparkles" size={14} color="primary" />
      </View>
      <View style={{ flex: 1, gap: 6 }}>
        {tools.length ? <ToolChips tools={tools} /> : null}
        {text ? <LiteMarkdown text={text} /> : null}
        {streaming && !text && !error ? (
          <Text tone="muted" variant="small">
            Thinking…
          </Text>
        ) : null}
        {status === "cancelled" ? (
          <Text tone="muted" variant="caption">
            Stopped.
          </Text>
        ) : null}
        {error ? (
          <Text tone="danger" variant="small" accessibilityRole="alert">
            {error.message}
          </Text>
        ) : null}
        {onRetry && (status === "failed" || error?.recoverable) ? (
          <Pressable
            accessibilityRole="button"
            onPress={onRetry}
            style={{
              flexDirection: "row",
              alignItems: "center",
              gap: 6,
              alignSelf: "flex-start",
              paddingVertical: 6,
            }}
          >
            <Icon name="refresh" size={16} color="primary" />
            <Text tone="primary" style={{ fontWeight: "600" }}>
              Retry
            </Text>
          </Pressable>
        ) : null}
      </View>
    </View>
  );
}

function ToolChips({
  tools,
}: {
  tools: (
    LiveTool | { name: string; ok?: boolean | null; summary?: string | null }
  )[];
}) {
  const { colors } = useTheme();
  return (
    <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6 }}>
      {tools.map((tool, index) => {
        const running = tool.ok === undefined;
        return (
          <View
            key={`${tool.name}-${index}`}
            style={{
              flexDirection: "row",
              alignItems: "center",
              gap: 4,
              borderRadius: radius.pill,
              borderWidth: 1,
              borderColor: colors.border,
              paddingHorizontal: 8,
              paddingVertical: 3,
            }}
          >
            {running ? (
              <ActivityIndicator size="small" />
            ) : (
              <Icon
                name={tool.ok ? "checkmark-circle" : "close-circle"}
                size={12}
                color={tool.ok ? "success" : "danger"}
              />
            )}
            <Text variant="caption" tone="muted">
              {TOOL_LABELS[tool.name] ?? tool.name}
              {tool.summary ? ` · ${tool.summary}` : ""}
            </Text>
          </View>
        );
      })}
    </View>
  );
}

function HistorySheet({
  visible,
  selected,
  onClose,
  onSelect,
}: {
  visible: boolean;
  selected: number | null;
  onClose: () => void;
  onSelect: (id: number | null) => void;
}) {
  const { colors } = useTheme();
  const conversations = useConversations();
  const remove = useDeleteConversation();
  return (
    <Sheet visible={visible} onClose={onClose} title="Conversations">
      <View style={{ gap: 4 }}>
        {conversations.isPending ? <ActivityIndicator /> : null}
        {conversations.data?.length === 0 ? (
          <Text tone="muted">No conversations yet.</Text>
        ) : null}
        {conversations.data?.map((c) => (
          <View
            key={c.id}
            style={{ flexDirection: "row", alignItems: "center" }}
          >
            <Pressable
              accessibilityRole="button"
              onPress={() => onSelect(c.id)}
              style={({ pressed }) => ({
                flex: 1,
                paddingVertical: 12,
                paddingHorizontal: 10,
                borderRadius: radius.md,
                backgroundColor:
                  c.id === selected
                    ? colors.primarySoft
                    : pressed
                      ? colors.surfaceRaised
                      : "transparent",
              })}
            >
              <Text
                numberOfLines={1}
                style={{ fontWeight: c.id === selected ? "600" : "400" }}
              >
                {c.title}
              </Text>
            </Pressable>
            <IconButton
              icon="trash-outline"
              label={`Delete ${c.title}`}
              tone="danger"
              onPress={() =>
                remove.mutate(c.id, {
                  onSuccess: () => c.id === selected && onSelect(null),
                })
              }
            />
          </View>
        ))}
      </View>
    </Sheet>
  );
}
