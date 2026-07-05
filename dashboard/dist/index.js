(function() {
  const SDK = window.__HERMES_PLUGIN_SDK__;
  if (!SDK) return;
  const { React } = SDK;
  const { useState, useEffect, useCallback } = React;
  const h = React.createElement;
  const { Card, CardContent, Badge, Button, Input, Label, Select, SelectOption } = SDK.components;

  const API = '/api/plugins/runtime-approval';
  const fetchJSON = SDK.fetchJSON;

  function RuntimeApprovalDashboard() {
    const [rules, setRules] = useState([]);
    const [tools, setTools] = useState({});
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const [newRule, setNewRule] = useState({
      tool: '',
      action: 'approve',
      fields: {},
      message: ''
    });

    const fetchData = useCallback(async () => {
      setLoading(true);
      setError(null);
      try {
        const [rulesData, toolsData] = await Promise.all([
          fetchJSON(`${API}/rules`),
          fetchJSON(`${API}/tools`)
        ]);
        setRules(rulesData || []);
        setTools(toolsData || {});
      } catch (e) {
        setError(String(e.message || e));
      } finally {
        setLoading(false);
      }
    }, []);

    useEffect(() => { fetchData(); }, [fetchData]);

    async function addRule() {
      if (!newRule.tool) { alert('Select a tool first'); return; }
      try {
        const updated = await fetchJSON(`${API}/rules`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(newRule)
        });
        setRules(updated || []);
        setNewRule({ tool: '', action: 'approve', fields: {}, message: '' });
      } catch (e) {
        alert(`Error adding rule: ${e.message || e}`);
      }
    }

    async function deleteRule(index) {
      try {
        const updated = await fetchJSON(`${API}/rules/${index}`, { method: 'DELETE' });
        setRules(updated || []);
      } catch (e) {
        alert(`Error deleting rule: ${e.message || e}`);
      }
    }

    if (loading) {
      return h('div', { style: { padding: '24px' } }, 'Loading Runtime Approval rules...');
    }

    if (error) {
      return h('div', { style: { padding: '24px', color: 'var(--destructive)' } }, `Error: ${error}`);
    }

    const matchableFields = tools[newRule.tool] || [];

    return h('div', { style: { padding: '24px', maxWidth: '900px', margin: '0 auto' } }, [
      // Header
      h('div', { style: { marginBottom: '24px' } }, [
        h('h1', { style: { fontSize: '24px', fontWeight: 'bold', marginBottom: '8px' } }, 'Runtime Approval'),
        h('p', { style: { opacity: '0.7', fontSize: '14px' } },
          'Runtime-enforced approval rules. The LLM cannot bypass these.')
      ]),

      // Active Rules
      h(Card, { style: { marginBottom: '24px' } }, [
        h(CardContent, { style: { padding: '16px' } }, [
          h('h3', { style: { marginBottom: '16px', fontSize: '16px', fontWeight: '600' } }, 'Active Rules'),
          rules.length === 0
            ? h('p', { style: { opacity: '0.6', fontSize: '14px' } }, 'No approval rules configured.')
            : h('div', { style: { display: 'flex', flexDirection: 'column', gap: '8px' } },
                rules.map(function (rule, idx) {
                  return h('div', {
                    key: idx,
                    style: {
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '12px',
                      borderRadius: '8px',
                      border: '1px solid var(--border)'
                    }
                  }, [
                    h('div', { style: { display: 'flex', flexDirection: 'column', gap: '4px' } }, [
                      h('div', { style: { display: 'flex', gap: '8px', alignItems: 'center' } }, [
                        h(Badge, { variant: 'outline' }, rule.tool),
                        h(Badge, {
                          variant: rule.action === 'approve' ? 'outline' : 'destructive'
                        }, rule.action === 'approve' ? 'Approve' : 'Block'),
                      ]),
                      h('div', { style: { fontSize: '12px', opacity: '0.6' } },
                        Object.entries(rule.fields || {}).map(function (entry) {
                          return h('span', { key: entry[0], style: { marginRight: '8px' } },
                            entry[0] + ': ' + entry[1]);
                        })
                      ),
                      rule.message ? h('div', { style: { fontSize: '12px', opacity: '0.7' } }, rule.message) : null
                    ]),
                    h(Button, {
                      variant: 'destructive',
                      onClick: function () { deleteRule(idx); }
                    }, 'Delete')
                  ]);
                })
              )
        ])
      ]),

      // Add Rule Form
      h(Card, { style: { marginBottom: '24px' } }, [
        h(CardContent, { style: { padding: '16px' } }, [
          h('h3', { style: { marginBottom: '16px', fontSize: '16px', fontWeight: '600' } }, 'Add New Rule'),

          // Tool dropdown
          h('div', { style: { marginBottom: '16px' } }, [
            h(Label, { style: { display: 'block', marginBottom: '4px' } }, 'Tool'),
            h(Select, {
              value: newRule.tool,
              onChange: function (e) { setNewRule(Object.assign({}, newRule, { tool: e.target.value })); },
              style: { width: '100%' }
            },
              h(SelectOption, { value: '', key: '__none' }, 'Select a tool...'),
              Object.keys(tools).map(function (tool) {
                return h(SelectOption, { value: tool, key: tool }, tool);
              })
            )
          ]),

          // Action dropdown
          h('div', { style: { marginBottom: '16px' } }, [
            h(Label, { style: { display: 'block', marginBottom: '4px' } }, 'Action'),
            h(Select, {
              value: newRule.action,
              onChange: function (e) { setNewRule(Object.assign({}, newRule, { action: e.target.value })); },
              style: { width: '100%' }
            }, [
              h(SelectOption, { value: 'approve', key: 'approve' }, 'Approve (human gate)'),
              h(SelectOption, { value: 'block', key: 'block' }, 'Block (unconditional)')
            ])
          ]),

          // Field patterns (dynamic)
          h('div', { style: { marginBottom: '16px' } }, [
            h(Label, { style: { display: 'block', marginBottom: '4px' } }, 'Field Matching (Regex)'),
            matchableFields.length === 0
              ? h('p', { style: { opacity: '0.5', fontSize: '13px' } }, 'Select a tool to see matchable fields.')
              : h('div', { style: { display: 'flex', flexDirection: 'column', gap: '8px' } },
                  matchableFields.map(function (field) {
                    return h('div', { key: field, style: { display: 'flex', flexDirection: 'column', gap: '2px' } }, [
                      h(Label, { style: { fontSize: '12px', opacity: '0.7' } }, field),
                      h(Input, {
                        value: newRule.fields[field] || '',
                        onChange: function (e) {
                          var updated = Object.assign({}, newRule.fields);
                          updated[field] = e.target.value;
                          if (!e.target.value) delete updated[field];
                          setNewRule(Object.assign({}, newRule, { fields: updated }));
                        },
                        placeholder: 'Regex pattern (empty = match all)'
                      })
                    ]);
                  })
                )
          ]),

          // Message
          h('div', { style: { marginBottom: '16px' } }, [
            h(Label, { style: { display: 'block', marginBottom: '4px' } }, 'Message'),
            h(Input, {
              value: newRule.message,
              onChange: function (e) { setNewRule(Object.assign({}, newRule, { message: e.target.value })); },
              placeholder: 'Reason shown in the approval prompt'
            })
          ]),

          // Submit
          h(Button, {
            onClick: addRule
          }, 'Add Rule')
        ])
      ]),

      // Info panel
      h('div', {
        style: {
          padding: '16px',
          borderRadius: '8px',
          border: '1px solid var(--border)',
          fontSize: '13px',
          opacity: '0.8'
        }
      }, [
        h('strong', null, 'Information: '),
        'Runtime gate = technically enforced at runtime. The LLM cannot skip or bypass it. ',
        'Prompt-only = instruction in system prompt, can be ignored.'
      ])
    ]);
  }

  if (window.__HERMES_PLUGINS__ && typeof window.__HERMES_PLUGINS__.register === 'function') {
    window.__HERMES_PLUGINS__.register('runtime-approval', RuntimeApprovalDashboard);
  }
})();