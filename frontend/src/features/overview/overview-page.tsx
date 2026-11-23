import { ArrowRight, AudioLines, CircleCheck, RefreshCw, ShieldCheck } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useHealth } from './api/health'

export function OverviewPage() {
  const health = useHealth()
  const connected = health.isSuccess && health.data.status.toLowerCase() === 'ok'

  return (
    <div className="overview-stack">
      <section className="hero-panel">
        <div className="hero-copy">
          <p className="eyebrow">EMI Voice Agent</p>
          <h2>Every customer conversation, prepared with intent.</h2>
          <p>Run and observe your agent-led EMI reminder workflow from one deliberate operations workspace.</p>
          <Link className="primary-action" to="/simulator">
            Open Live Simulator <ArrowRight size={17} />
          </Link>
        </div>
        <div className="signal-card">
          <div className="signal-icon"><AudioLines size={23} /></div>
          <p>System readiness</p>
          <strong>
            {health.isPending ? 'Checking service' : connected ? 'Backend API responding' : 'Service needs attention'}
          </strong>
          <span className={connected ? 'status-good' : 'status-caution'}>
            {connected ? <CircleCheck size={15} /> : <RefreshCw size={15} />}
            {connected ? 'Health endpoint responding' : health.isPending ? 'Verifying live connection' : 'Unable to reach health endpoint'}
          </span>
        </div>
      </section>
      <section className="section-heading">
        <div>
          <p className="eyebrow">Operations foundation</p>
          <h2>Purpose-built for responsible outreach</h2>
        </div>
        <p>Use the simulator to validate a text-based agent conversation before expanding into live operational workflows.</p>
      </section>
      <section className="workflow-grid">
        <article>
          <span><AudioLines size={18} /></span>
          <h3>Conversation workspace</h3>
          <p>Start a controlled session, capture text interactions, and follow the agent's conversation state.</p>
        </article>
        <article>
          <span><ShieldCheck size={18} /></span>
          <h3>Human handoff</h3>
          <p>Keep room for exception handling and specialist follow-up as escalation services are connected.</p>
        </article>
        <article>
          <span><RefreshCw size={18} /></span>
          <h3>Operational visibility</h3>
          <p>See real service availability now, with history and disposition integration ready for future endpoints.</p>
        </article>
      </section>
    </div>
  )
}
