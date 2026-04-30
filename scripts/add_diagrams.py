"""Add one unique inline SVG diagram to each of the 6 case study pages."""
import os

SITE = os.path.join(os.path.dirname(__file__), '..', 'site')

# ── Shared CSS (replaces old diagram-wrap in coding-assistant, added to others) ──
DIAGRAM_CSS_OLD = (
    "    .diagram-wrap { max-width: 960px; margin: 0 auto; padding: 0 2rem 0; }\n"
    "    .diagram-wrap svg { display: block; width: 100%; overflow: visible; }"
)
DIAGRAM_CSS_NEW = (
    "    .diagram-wrap { max-width: 960px; margin: 3rem auto 0; padding: 3rem 2rem 0;"
    " border-top: 1px solid rgba(255,255,255,0.06); }\n"
    "    .diagram-wrap svg { display: block; width: 100%; overflow: visible; }"
)
DIAGRAM_CSS_INJECT = (
    "\n    .diagram-wrap { max-width: 960px; margin: 3rem auto 0; padding: 3rem 2rem 0;"
    " border-top: 1px solid rgba(255,255,255,0.06); }\n"
    "    .diagram-wrap svg { display: block; width: 100%; overflow: visible; }"
)

# ── Template: 3-node + pass/fail (used for 4 pages) ─────────────────────────
def pf_diagram(eyebrow, node_a_sub, node_a_main,
               mneme_label, mneme_sub,
               node_b_sub, node_b_main,
               pass_label, fail_label):
    """
    viewBox 0 0 960 200
    Node A  (x=20, w=165, cx=102)
    Mneme   (x=225, w=215, cx=332)  accent border
    Node B  (x=480, w=185, cx=572)  teal border
    Pass box (x=10, w=184, cx=102)
    Fail box (x=478, w=188, cx=572)
    Horizontal branch: x1=102 x2=572
    """
    return f'''\
  <div class="diagram-wrap">
    <svg viewBox="0 0 960 200" fill="none" xmlns="http://www.w3.org/2000/svg">
      <text x="20" y="14" font-family="monospace" font-size="9" fill="#88889a" letter-spacing="4">{eyebrow}</text>
      <!-- Node A -->
      <rect x="20" y="30" width="165" height="56" rx="8" fill="#141416" stroke="#2e2e34" stroke-width="1.5"/>
      <text x="102" y="52" font-family="monospace" font-size="9.5" fill="#88889a" text-anchor="middle">{node_a_sub}</text>
      <text x="102" y="72" font-family="monospace" font-size="13" fill="#e8e8ec" text-anchor="middle">{node_a_main}</text>
      <!-- Arrow A→Mneme -->
      <line x1="185" y1="58" x2="218" y2="58" stroke="#2e2e34" stroke-width="1.5"/>
      <polygon points="214,54 225,58 214,62" fill="#2e2e34"/>
      <!-- Mneme node -->
      <rect x="225" y="18" width="215" height="80" rx="8" fill="#141416" stroke="#c8f060" stroke-width="1.5"/>
      <text x="332" y="42" font-family="monospace" font-size="9" fill="#c8f060" text-anchor="middle" letter-spacing="4">MNEME</text>
      <text x="332" y="64" font-family="monospace" font-size="13" fill="#e8e8ec" text-anchor="middle">{mneme_label}</text>
      <text x="332" y="82" font-family="monospace" font-size="9" fill="#88889a" text-anchor="middle">{mneme_sub}</text>
      <!-- Arrow Mneme→B -->
      <line x1="440" y1="58" x2="473" y2="58" stroke="#2e2e34" stroke-width="1.5"/>
      <polygon points="469,54 480,58 469,62" fill="#2e2e34"/>
      <!-- Node B -->
      <rect x="480" y="30" width="185" height="56" rx="8" fill="#141416" stroke="#8be0c8" stroke-width="1.5"/>
      <text x="572" y="52" font-family="monospace" font-size="9.5" fill="#8be0c8" text-anchor="middle">{node_b_sub}</text>
      <text x="572" y="72" font-family="monospace" font-size="13" fill="#e8e8ec" text-anchor="middle">{node_b_main}</text>
      <!-- Vertical drop from Mneme -->
      <line x1="332" y1="98" x2="332" y2="124" stroke="#2e2e34" stroke-width="1.5"/>
      <!-- Horizontal branch (pass-cx=102, fail-cx=572) -->
      <line x1="102" y1="124" x2="572" y2="124" stroke="#2e2e34" stroke-width="1.5"/>
      <!-- Branch down to pass -->
      <line x1="102" y1="124" x2="102" y2="136" stroke="#c8f060" stroke-width="1.5"/>
      <!-- Branch down to fail -->
      <line x1="572" y1="124" x2="572" y2="136" stroke="#ff7070" stroke-width="1.5"/>
      <!-- Pass box -->
      <rect x="10" y="136" width="184" height="40" rx="6" fill="#0d1a08" stroke="#1e3310" stroke-width="1"/>
      <text x="102" y="153" font-family="monospace" font-size="11" fill="#c8f060" text-anchor="middle">&#x2713; Pass</text>
      <text x="102" y="169" font-family="monospace" font-size="9" fill="#88889a" text-anchor="middle">{pass_label}</text>
      <!-- Fail box -->
      <rect x="478" y="136" width="188" height="40" rx="6" fill="#1a0808" stroke="#331010" stroke-width="1"/>
      <text x="572" y="153" font-family="monospace" font-size="11" fill="#ff7070" text-anchor="middle">&#x2717; Fail</text>
      <text x="572" y="169" font-family="monospace" font-size="9" fill="#88889a" text-anchor="middle">{fail_label}</text>
    </svg>
  </div>'''


# ── Diagram definitions per page ─────────────────────────────────────────────

DIAGRAMS = {}

# 1. Coding Assistant Governance
DIAGRAMS['coding-assistant-governance'] = pf_diagram(
    eyebrow       = 'ENFORCEMENT FLOW',
    node_a_sub    = 'developer', node_a_main = 'Prompt',
    mneme_label   = 'Pre-flight Check', mneme_sub = 'mneme check --mode strict',
    node_b_sub    = 'decisions/', node_b_main = 'Decision Store',
    pass_label    = 'AI generates compliant code',
    fail_label    = 'Violation surfaced before generation',
)

# 2. Legacy Codebase Memory — 4-node linear capture pipeline
DIAGRAMS['legacy-codebase-memory'] = '''\
  <div class="diagram-wrap">
    <svg viewBox="0 0 960 118" fill="none" xmlns="http://www.w3.org/2000/svg">
      <text x="20" y="14" font-family="monospace" font-size="9" fill="#88889a" letter-spacing="4">CAPTURE &amp; ENFORCE PIPELINE</text>
      <!-- Node 1: Tribal Knowledge -->
      <rect x="10" y="24" width="195" height="60" rx="8" fill="#141416" stroke="#2e2e34" stroke-width="1.5"/>
      <text x="107" y="46" font-family="monospace" font-size="9.5" fill="#88889a" text-anchor="middle">tribal knowledge</text>
      <text x="107" y="66" font-family="monospace" font-size="12" fill="#e8e8ec" text-anchor="middle">Undocumented Rules</text>
      <text x="107" y="80" font-family="monospace" font-size="8.5" fill="#88889a" text-anchor="middle">Slack, memory, post-mortems</text>
      <!-- Arrow 1→2 -->
      <line x1="205" y1="54" x2="240" y2="54" stroke="#2e2e34" stroke-width="1.5"/>
      <polygon points="236,50 247,54 236,58" fill="#2e2e34"/>
      <!-- Node 2: Capture Session -->
      <rect x="247" y="24" width="185" height="60" rx="8" fill="#141416" stroke="#2e2e34" stroke-width="1.5"/>
      <text x="339" y="46" font-family="monospace" font-size="9.5" fill="#88889a" text-anchor="middle">30-min session</text>
      <text x="339" y="66" font-family="monospace" font-size="12" fill="#e8e8ec" text-anchor="middle">Capture Session</text>
      <text x="339" y="80" font-family="monospace" font-size="8.5" fill="#88889a" text-anchor="middle">mneme add → decisions/*.yml</text>
      <!-- Arrow 2→3 -->
      <line x1="432" y1="54" x2="467" y2="54" stroke="#2e2e34" stroke-width="1.5"/>
      <polygon points="463,50 474,54 463,58" fill="#2e2e34"/>
      <!-- Node 3: Decision Store (teal) -->
      <rect x="474" y="24" width="185" height="60" rx="8" fill="#141416" stroke="#8be0c8" stroke-width="1.5"/>
      <text x="566" y="46" font-family="monospace" font-size="9.5" fill="#8be0c8" text-anchor="middle">decisions/</text>
      <text x="566" y="66" font-family="monospace" font-size="12" fill="#e8e8ec" text-anchor="middle">Decision Store</text>
      <text x="566" y="80" font-family="monospace" font-size="8.5" fill="#88889a" text-anchor="middle">structured, retrievable, versioned</text>
      <!-- Arrow 3→4 -->
      <line x1="659" y1="54" x2="694" y2="54" stroke="#2e2e34" stroke-width="1.5"/>
      <polygon points="690,50 701,54 690,58" fill="#2e2e34"/>
      <!-- Node 4: AI Enforcement (accent) -->
      <rect x="701" y="24" width="195" height="60" rx="8" fill="#141416" stroke="#c8f060" stroke-width="1.5"/>
      <text x="798" y="46" font-family="monospace" font-size="9.5" fill="#c8f060" text-anchor="middle">every session</text>
      <text x="798" y="66" font-family="monospace" font-size="12" fill="#e8e8ec" text-anchor="middle">AI Enforcement</text>
      <text x="798" y="80" font-family="monospace" font-size="8.5" fill="#88889a" text-anchor="middle">mneme check before every prompt</text>
    </svg>
  </div>'''

# 3. Security & Compliance Guardrails
DIAGRAMS['security-compliance-guardrails'] = pf_diagram(
    eyebrow       = 'SECURITY ENFORCEMENT FLOW',
    node_a_sub    = 'AI-assisted', node_a_main = 'Code Request',
    mneme_label   = 'Security Filter', mneme_sub = 'mneme check --tags security,gdpr',
    node_b_sub    = 'compliance', node_b_main = 'Policy Decisions',
    pass_label    = 'Generation proceeds — compliant',
    fail_label    = 'PII / auth violation blocked',
)

# 4. Data Platform Governance
DIAGRAMS['data-platform-governance'] = pf_diagram(
    eyebrow       = 'DATA CONTRACT ENFORCEMENT',
    node_a_sub    = 'AI pipeline', node_a_main = 'Prompt',
    mneme_label   = 'Data Contract Check', mneme_sub = 'mneme check --tags data-platform',
    node_b_sub    = 'layer &amp; schema', node_b_main = 'Architecture Rules',
    pass_label    = 'Write to staging.* approved',
    fail_label    = 'raw.* write blocked',
)

# 5. Design System Governance
DIAGRAMS['design-system-governance'] = pf_diagram(
    eyebrow       = 'DESIGN ENFORCEMENT FLOW',
    node_a_sub    = 'UI generation', node_a_main = 'Prompt',
    mneme_label   = 'Design Token Filter', mneme_sub = 'mneme check --tags design-system',
    node_b_sub    = 'token &amp; component', node_b_main = 'Design Rules',
    pass_label    = 'Compliant JSX generated',
    fail_label    = 'Token / ARIA violations flagged',
)

# 6. Multi-Agent Workflow Governance — hub & spoke
DIAGRAMS['multi-agent-workflow-governance'] = '''\
  <div class="diagram-wrap">
    <svg viewBox="0 0 840 290" fill="none" xmlns="http://www.w3.org/2000/svg">
      <text x="20" y="14" font-family="monospace" font-size="9" fill="#88889a" letter-spacing="4">SHARED DECISION LAYER</text>
      <!-- Agent pipeline (left column) -->
      <!-- Stage 1: Planner -->
      <rect x="10" y="22" width="210" height="52" rx="8" fill="#141416" stroke="#2e2e34" stroke-width="1.5"/>
      <text x="115" y="41" font-family="monospace" font-size="9" fill="#88889a" text-anchor="middle">Stage 1</text>
      <text x="115" y="60" font-family="monospace" font-size="13" fill="#e8e8ec" text-anchor="middle">Planner Agent</text>
      <!-- Down arrow -->
      <line x1="115" y1="74" x2="115" y2="92" stroke="#2e2e34" stroke-width="1.5"/>
      <polygon points="111,88 115,98 119,88" fill="#2e2e34"/>
      <!-- Stage 2: Coder -->
      <rect x="10" y="98" width="210" height="52" rx="8" fill="#141416" stroke="#2e2e34" stroke-width="1.5"/>
      <text x="115" y="117" font-family="monospace" font-size="9" fill="#88889a" text-anchor="middle">Stage 2</text>
      <text x="115" y="136" font-family="monospace" font-size="13" fill="#e8e8ec" text-anchor="middle">Coder Agent</text>
      <!-- Down arrow -->
      <line x1="115" y1="150" x2="115" y2="168" stroke="#2e2e34" stroke-width="1.5"/>
      <polygon points="111,164 115,174 119,164" fill="#2e2e34"/>
      <!-- Stage 3: Reviewer -->
      <rect x="10" y="174" width="210" height="52" rx="8" fill="#141416" stroke="#2e2e34" stroke-width="1.5"/>
      <text x="115" y="193" font-family="monospace" font-size="9" fill="#88889a" text-anchor="middle">Stage 3</text>
      <text x="115" y="212" font-family="monospace" font-size="13" fill="#e8e8ec" text-anchor="middle">Reviewer Agent</text>
      <!-- Down arrow -->
      <line x1="115" y1="226" x2="115" y2="244" stroke="#2e2e34" stroke-width="1.5"/>
      <polygon points="111,240 115,250 119,240" fill="#2e2e34"/>
      <!-- Stage 4: Deployer -->
      <rect x="10" y="250" width="210" height="30" rx="8" fill="#141416" stroke="#2e2e34" stroke-width="1.5"/>
      <text x="115" y="270" font-family="monospace" font-size="13" fill="#88889a" text-anchor="middle">Deployer Agent</text>
      <!-- Mneme store (right, tall) -->
      <rect x="490" y="18" width="240" height="254" rx="10" fill="#141416" stroke="#c8f060" stroke-width="1.5"/>
      <text x="610" y="52" font-family="monospace" font-size="9" fill="#c8f060" text-anchor="middle" letter-spacing="4">MNEME</text>
      <text x="610" y="80" font-family="monospace" font-size="15" fill="#e8e8ec" text-anchor="middle">Decision Store</text>
      <text x="610" y="104" font-family="monospace" font-size="9" fill="#88889a" text-anchor="middle">decisions/*.yml</text>
      <!-- Divider -->
      <line x1="510" y1="118" x2="710" y2="118" stroke="#222226" stroke-width="1"/>
      <text x="610" y="138" font-family="monospace" font-size="8.5" fill="#88889a" text-anchor="middle">shared across all stages</text>
      <text x="610" y="158" font-family="monospace" font-size="8.5" fill="#88889a" text-anchor="middle">semantic retrieval per query</text>
      <text x="610" y="178" font-family="monospace" font-size="8.5" fill="#88889a" text-anchor="middle">violations block next stage</text>
      <text x="610" y="198" font-family="monospace" font-size="8.5" fill="#88889a" text-anchor="middle">full audit trail per run</text>
      <!-- Connection lines from each agent right edge → Mneme left edge -->
      <!-- Planner (right=220, cy=48) → Mneme left (490, 75) -->
      <line x1="220" y1="48" x2="490" y2="75" stroke="#2e2e34" stroke-width="1" stroke-dasharray="4 3"/>
      <text x="345" y="54" font-family="monospace" font-size="8" fill="#88889a" text-anchor="middle">check()</text>
      <!-- Coder (right=220, cy=124) → Mneme left (490, 124) -->
      <line x1="220" y1="124" x2="490" y2="145" stroke="#2e2e34" stroke-width="1" stroke-dasharray="4 3"/>
      <text x="352" y="128" font-family="monospace" font-size="8" fill="#88889a" text-anchor="middle">check()</text>
      <!-- Reviewer (right=220, cy=200) → Mneme left (490, 195) -->
      <line x1="220" y1="200" x2="490" y2="195" stroke="#2e2e34" stroke-width="1" stroke-dasharray="4 3"/>
      <text x="352" y="195" font-family="monospace" font-size="8" fill="#88889a" text-anchor="middle">check()</text>
      <!-- Deployer (right=220, cy=265) → Mneme left (490, 240) -->
      <line x1="220" y1="265" x2="490" y2="245" stroke="#2e2e34" stroke-width="1" stroke-dasharray="4 3"/>
      <text x="345" y="262" font-family="monospace" font-size="8" fill="#88889a" text-anchor="middle">check()</text>
    </svg>
  </div>'''


# ── Apply to each page ────────────────────────────────────────────────────────

INSERT_BEFORE = {
    'coding-assistant-governance':      '  <!-- PROBLEM -->',
    'legacy-codebase-memory':           '  <!-- PROBLEM -->',
    'security-compliance-guardrails':   '  <!-- PROBLEM -->',
    'data-platform-governance':         '  <div class="section-wrap">',
    'design-system-governance':         '  <div class="section-wrap">',
    'multi-agent-workflow-governance':  '  <div class="section-wrap">',
}

for slug, diagram_html in DIAGRAMS.items():
    path = os.path.join(SITE, 'use-cases', slug, 'index.html')
    with open(path, encoding='utf-8') as f:
        html = f.read()

    # 1. Fix / add diagram CSS
    if DIAGRAM_CSS_OLD in html:
        html = html.replace(DIAGRAM_CSS_OLD, DIAGRAM_CSS_NEW)
    elif '.diagram-wrap' not in html:
        html = html.replace('  </style>', DIAGRAM_CSS_INJECT + '\n  </style>', 1)

    # 2. Remove old diagram block if present (coding-assistant only)
    if '<!-- DIAGRAM:' in html:
        start = html.index('  <!-- DIAGRAM:')
        end   = html.index('  <!-- PROBLEM -->')
        html  = html[:start] + html[end:]

    # 3. Insert new diagram before anchor
    anchor = INSERT_BEFORE[slug]
    if anchor in html:
        html = html.replace(anchor, diagram_html + '\n\n  ' + anchor.strip(), 1)
    else:
        print(f'  WARNING: anchor not found for {slug}')
        continue

    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'  {slug}: done')

print('\nAll diagrams applied.')
