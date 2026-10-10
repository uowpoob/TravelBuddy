import { AlertCircle, CheckCircle2, Circle, Clock3, LoaderCircle } from 'lucide-react'
import type { PlanningNodeStatus, PlanningProgress } from '../../types/conversation'

const names: Record<string, string> = {
  understand: '理解旅行需求',
  clarify: '补充旅行信息',
  researcher: '调研地点',
  context_analyst: '分析出行条件',
  planner: '安排路线与行程',
  reviewer: '检查旅行方案',
  confirm: '确认旅行方案',
  save: '保存行程',
}
const nodeLabels: Record<PlanningNodeStatus, string> = {
  pending: '本轮未执行',
  running: '执行中',
  completed: '已完成',
  failed: '失败',
  waiting: '等待你的回答',
}
export const progressLabels = {
  idle: '还没有规划记录',
  running: '正在规划旅程',
  waiting_clarification: '等待补充旅行需求',
  waiting_approval: '等待确认旅行方案',
  completed: '本轮规划已完成',
  failed: '规划已停止',
}

export function PlanningProgressPanel({ progress }: { progress: PlanningProgress }) {
  return (
    <section className="panel planning-progress" aria-label="规划节点状态" aria-live="polite">
      <h2>{progressLabels[progress.status]}</h2>
      {progress.error && (
        <p className="conversation-error" role="alert">
          {progress.error}
        </p>
      )}
      <ol className="planning-nodes">
        {Object.entries(progress.nodes).map(([name, status]) => {
          const Icon =
            status === 'running'
              ? LoaderCircle
              : status === 'completed'
                ? CheckCircle2
                : status === 'failed'
                  ? AlertCircle
                  : status === 'waiting'
                    ? Clock3
                    : Circle
          return (
            <li key={name} className={`planning-node planning-${status}`}>
              <Icon size={18} className={status === 'running' ? 'spin' : ''} />
              <span>{names[name] || name}</span>
              <small>{nodeLabels[status]}</small>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
