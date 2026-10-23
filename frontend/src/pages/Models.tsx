import { useModels } from "../api/hooks";
import { Badge, Card, Empty, ErrorBox, PageHeader, Spinner } from "../components/ui";

const CAPABILITY_LABEL: Record<string, string> = {
  chat: "Chat Completions",
  streaming: "Streaming",
  responses: "Responses API",
  tool_calling: "Tool calling",
  session_persistence: "Сессии",
  images: "Изображения",
};

export default function Models() {
  const models = useModels();

  if (models.isLoading) return <Spinner />;
  if (models.error) return <ErrorBox error={models.error} />;

  return (
    <div>
      <PageHeader
        title="Модели"
        subtitle="Реестр моделей и фактически проверенные возможности"
      />
      {!models.data?.length ? (
        <Card>
          <Empty>Модели не зарегистрированы</Empty>
        </Card>
      ) : (
        <div className="grid gap-5 lg:grid-cols-2">
          {models.data.map((model) => (
            <Card key={model.id}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold">{model.display_name}</h2>
                  <div className="mt-0.5 font-mono text-xs" style={{ color: "var(--muted)" }}>
                    {model.id}
                  </div>
                </div>
                <Badge status={model.upstream === "mock" ? "EXPERIMENTAL" : "UNKNOWN"}>
                  {model.upstream}
                </Badge>
              </div>
              <dl className="mt-4 space-y-2 text-sm">
                {Object.entries(model.capabilities).map(([name, status]) => (
                  <div key={name} className="flex items-center justify-between gap-3">
                    <dt style={{ color: "var(--muted)" }}>{CAPABILITY_LABEL[name] ?? name}</dt>
                    <dd>
                      <Badge status={status} />
                    </dd>
                  </div>
                ))}
              </dl>
              {model.upstream === "mock" ? (
                <p className="mt-4 rounded-xl px-3 py-2 text-xs" style={{ background: "var(--panel-2)", color: "var(--muted)" }}>
                  Mock-модель отвечает детерминированно и не обращается к Google. Проверка реального
                  AI Mode имеет статус UNSUPPORTED в текущих границах.
                </p>
              ) : null}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

