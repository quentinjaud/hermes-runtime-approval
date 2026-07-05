(function() {
  const SDK = window.__HERMES_PLUGIN_SDK__;
  if (!SDK) return;
  const { React } = SDK;
  const { useState, useEffect } = React;
  const h = React.createElement;
  const { Card, CardContent, Badge, Button, Input, Label, Select, SelectOption } = SDK.components;

  const API_BASE = '/api/plugins/runtime-approval';

  function RuntimeApprovalDashboard() {
    const [rules, setRules] = useState([]);
    const [tools, setTools] = useState({});
    const [loading, setLoading] = useState(true);
    
    const [newRule, setNewRule] = useState({
      tool: '',
      action: 'approve',
      fields: {},
      message: ''
    });

    async function fetchData() {
      setLoading(true);
      try {
        const [rulesRes, toolsRes] = await Promise.all([
          fetch(`${API_BASE}/rules`),
          fetch(`${API_BASE}/tools`)
        ]);
        setRules(await rulesRes.json());
        setTools(await toolsRes.json());
      } catch (e) {
        console.error('Failed to fetch dashboard data:', e);
      } finally {
        setLoading(false);
      }
    }

    useEffect(() => {
      fetchData();
    }, []);

    async function addRule() {
      try {
        const res = await fetch(`${API_BASE}/rules`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(newRule)
        });
        if (res.ok) {
          const updatedRules = await res.json();
          setRules(updatedRules);
          setNewRule({ tool: '', action: 'approve', fields: {}, message: '' });
        } else {
          const err = await res.json();
          alert(`Error adding rule: ${err.detail || 'Unknown error'}`);
        }
      } catch (e) {
        console.error('Error adding rule:', e);
      }
    }

    async function deleteRule(index) {
      try {
        const res = await fetch(`${API_BASE}/rules/${index}`, { method: 'DELETE' });
        if (res.ok) {
          const updatedRules = await res.json();
          setRules(updatedRules);
        }
      } catch (e) {
        console.error('Error deleting rule:', e);
      }
    }

    if (loading) return h('div', { style: { padding: '20px', textAlign: 'center' } }, 'Loading Runtime Approval Rules...');

    const matchableFields = tools[newRule.tool] || [];

    return h('div', { style: { padding: '20px', maxWidth: '1000px', margin: '0 auto', color: 'var(--text-primary)' } }, [
      h('div', { style: { marginBottom: '24px' } }, [
        h('h1', { style: { fontSize: '24px', fontWeight: 'bold', marginBottom: '8px' } }, 'Runtime Approval'),
        h('p', { style: { color: 'var(--text-secondary)', fontSize: '14px' } }, 'Runtime-enforced approval rules. The LLM cannot bypass these.')
      ]),

      h(Card, { style: { marginBottom: '24px' } }, [
        h(CardContent, {}, [
          h('h3', { style: { marginBottom: '16px', fontSize: '18px' } }, 'Active Rules'),
          rules.length === 0 
            ? h('p', { style: { color: 'var(--text-secondary)', fontSize: '14px' } }, 'No approval rules configured.')
            : h('div', { style: { display: 'flex', flexDirection: 'column', gap: '12px' } }, 
                rules.map((rule, idx) => h('div', { 
                  key: idx, 
                  style: { 
                    display: 'flex', 
                    alignItems: 'center', 
                    justifyContent: 'space-between', 
                    padding: '12px', 
                    backgroundColor: 'var(--bg-secondary)', 
                    borderRadius: '8px',
                    border: '1px solid var(--border-color)' 
                  } 
                }, [
                  h('div', { style: { display: 'flex', flexDirection: 'column', gap: '4px' } }, [
                    h('div', { style: { display: 'flex', gap: '8px', alignItems: 'center' } }, [
                      h(Badge, { children: rule.tool, variant: 'default' }),
                      h(Badge, { 
                        children: rule.action === 'approve' ? 'Approve' : 'Block', 
                        variant: rule.action === 'approve' ? 'success' : 'danger' 
                      }),
                    ]),
                    h('div', { style: { fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' } }, [
                      Object.entries(rule.fields || {}).map(([field, pattern]) => 
                        h('span', { key: field, style: { marginRight: '8px' } }, `${field}: ${pattern}`)
                      ),
                      rule.message && h('div', { style: { display: 'block', marginTop: '2px' }, children: rule.message })
                    ])
                  ]),
                  h(Button, { 
                    onClick: () => deleteRule(idx), 
                    variant: 'ghost', 
                    style: { color: 'var(--text-danger)' } 
                  }, 'Delete')
                ])
              ))
        ])
      ]),

      h(Card, { style: { marginBottom: '24px' } }, [
        h(CardContent, {}, [
          h('h3', { style: { marginBottom: '16px', fontSize: '18px' } }, 'Add New Rule'),
          h('div', { style: { display: 'flex', flexDirection: 'column', gap: '16px' } }, [
            h('div', { style: { display: 'flex', flexDirection: 'column', gap: '8px' } }, [
              h(Label, { children: 'Tool' }),
              h(Select, { 
                value: newRule.tool, 
                onChange: (e) => setNewRule({ ...newRule, tool: e.target.value }),
                style: { width: '300px' }
              }, 
                Object.keys(tools).map(tool => h(SelectOption, { value: tool, key: tool }, tool))
              )
            ]),
            h('div', { style: { display: 'flex', flexDirection: 'column', gap: '8px' } }, [
              h(Label, { children: 'Action' }),
              h(Select, { 
                value: newRule.action, 
                onChange: (e) => setNewRule({ ...newRule, action: e.target.value }),
                style: { width: '300px' }
              }, [
                h(SelectOption, { value: 'approve', key: 'approve' }, 'Approve'),
                h(SelectOption, { value: 'block', key: 'block' }, 'Block')
              ])
            ]),
            h('div', { style: { display: 'flex', flexDirection: 'column', gap: '8px' } }, [
              h(Label, { children: 'Field Matching (Regex)' }),
              h('div', { style: { display: 'flex', flexDirection: 'column', gap: '12px' } }, 
                matchableFields.length === 0 
                  ? h('span', { style: { color: 'var(--text-secondary)', fontSize: '14px' } }, 'Select a tool to see matchable fields.')
                  : matchableFields.map(field => h('div', { 
                      key: field, 
                      style: { display: 'flex', flexDirection: 'column', gap: '4px' } 
                    }, [
                      h(Label, { children: field, style: { fontSize: '12px' } }),
                      h(Input, { 
                        value: newRule.fields[field] || '', 
                        onChange: (e) => {
                          const updatedFields = { ...newRule.fields, [field]: e.target.value };
                          setNewRule({ ...newRule, fields: updatedFields });
                        },
                        placeholder: 'Regex pattern (empty = match all)'
                      })
                    ]))
              )
            ]),
            h('div', { style: { display: 'flex', flexDirection: 'column', gap: '8px' } }, [
              h(Label, { children: 'Message' }),
              h(Input, { 
                value: newRule.message, 
                onChange: (e) => setNewRule({ ...newRule, message: e.target.value }),
                placeholder: 'Reason or instruction for the user'
              })
            ]),
            h(Button, { 
              onClick: addRule, 
              variant: 'primary', 
              style: { width: '200px', alignSelf: 'flex-start' } 
            }, 'Add Rule')
          ])
        ])
      ]),

      h('div', { 
        style: { 
          padding: '16px', 
          backgroundColor: 'var(--bg-secondary)', 
          borderRadius: '8px', 
          border: '1px solid var(--border-color)',
          fontSize: '13px',
          color: 'var(--text-secondary)' 
        } 
      }, [
        h('strong', { style: { color: 'var(--text-primary)' } }, 'Information: '),
        'Runtime gate = technically enforced at runtime. The LLM cannot skip or bypass it. Prompt-only = instruction in system prompt, can be ignored.'
      ])
    ]);
  }

  SDK.registerPluginDashboard('runtime-approval', RuntimeApprovalDashboard);
})();
