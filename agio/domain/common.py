from pydantic import BaseModel, Field, ConfigDict

class GenerationReference(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    """指向生成该内容的 LLM 调用记录"""
    run_id: str  # 所属的 Run ID (可能是后台任务的 Run)
    step_id: str # 具体执行生成的 Step ID
    model_id: str
    # 关键参数快照，便于快速查看
    context_window_size: int | None = None 
    citations: list[str] = Field(default_factory=list)
