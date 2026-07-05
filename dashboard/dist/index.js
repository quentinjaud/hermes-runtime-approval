(function() {
  const SDK = window.__HERMES_PLUGIN_SDK__;
  if (!SDK) return;
  const { React } = SDK;
  const { useState, useEffect, useCallback } = React;
  const h = React.createElement;
  const { Card, CardContent, Badge, Button, Input, Label, Select, SelectOption } = SDK.components;

  const API = '/api/plugins/runtime-approval';
  const fetchJSON = SDK.fetchJSON;

  // Fallback matchable fields for known tools (used when the toolset API
  // doesn't expose parameter schemas). MCP and unknown tools get [].
  var MATCHABLE_FIELDS = {
    terminal: ['command', 'workdir'],
    execute_code: ['code'],
    write_file: ['path'],
    patch: ['path', 'old_string', 'new_string'],
    browser_type: ['ref', 'text'],
    browser_click: ['ref'],
    browser_navigate: ['url'],
  };

  function getMatchableFields(toolName) {
    return MATCHABLE_FIELDS[toolName] || [];
  }

  function RuntimeApprovalDashboard() {
    const [rules, setRules] = useState([]);
    const [allTools, setAllTools] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const [defaultAction, setDefaultAction] = useState(null);
    const [exemptTools, setExemptTools] = useState([]);

    const [newRule, setNewRule] = useState({ tool: '', action: 'approve', fields: {}, message: '' });
    const [dragTool, setDragTool] = useState(null);

    var fetchData = useCallback(async function () {
      setLoading(true);
      setError(null);
      try {
        var results = await Promise.all([
          fetchJSON(API + '/rules'),
          fetchJSON('/api/tools/toolsets'),
          fetchJSON(API + '/default-action'),
          fetchJSON(API + '/exempt-tools')
        ]);
        setRules(results[0] || []);
        // Flatten toolsets → sorted list of tool names
        var toolsets = results[1] || [];
        var tools = [];
        for (var i = 0; i < toolsets.length; i++) {
          var tsTools = toolsets[i].tools || [];
          for (var j = 0; j < tsTools.length; j++) {
            tools.push(tsTools[j]);
          }
        }
        tools.sort();
        setAllTools(tools);
        setDefaultAction((results[2] || {}).default_action || null);
        setExemptTools((results[3] || {}).exempt_tools || []);
      } catch (e) {
        setError(String(e.message || e));
      } finally {
        setLoading(false);
      }
    }, []);

    useEffect(function () { fetchData(); }, [fetchData]);

    async function addRule() {
      if (!newRule.tool) { alert('Select a tool first'); return; }
      try {
        var updated = await fetchJSON(API + '/rules', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(newRule)
        });
        setRules(updated || []);
        setNewRule({ tool: '', action: 'approve', fields: {}, message: '' });
      } catch (e) {
        alert('Error adding rule: ' + (e.message || e));
      }
    }

    async function deleteRule(index) {
      try {
        var updated = await fetchJSON(API + '/rules/' + index, { method: 'DELETE' });
        setRules(updated || []);
      } catch (e) {
        alert('Error deleting rule: ' + (e.message || e));
      }
    }

    async function saveDefaultAction(value) {
      try {
        var data = await fetchJSON(API + '/default-action', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ default_action: value })
        });
        setDefaultAction(data.default_action);
      } catch (e) {
        alert('Error setting default action: ' + (e.message || e));
      }
    }

    // Tools that require runtime approval = all tools NOT in exempt list
    function getApproveRequiredTools() {
      var exemptSet = {};
      exemptTools.forEach(function (t) { exemptSet[t] = true; });
      return allTools.filter(function (t) { return !exemptSet[t]; });
    }

    // Drag-and-drop: move tool to trusted (exempt)
    async function dropToTrusted(toolName) {
      if (exemptTools.indexOf(toolName) !== -1) return;
      var updated = exemptTools.concat([toolName]);
      try {
        var data = await fetchJSON(API + '/exempt-tools', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ exempt_tools: updated })
        });
        setExemptTools(data.exempt_tools || []);
      } catch (e) {
        alert('Error exempting tool: ' + (e.message || e));
      }
    }

    // Drag-and-drop: move tool back to approve-required (remove from exempt)
    async function dropToApproveRequired(toolName) {
      var updated = exemptTools.filter(function (t) { return t !== toolName; });
      try {
        var data = await fetchJSON(API + '/exempt-tools', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ exempt_tools: updated })
        });
        setExemptTools(data.exempt_tools || []);
      } catch (e) {
        alert('Error removing exempt tool: ' + (e.message || e));
      }
    }

    if (loading) {
      return h('div', { style: { padding: '24px' } }, 'Loading Runtime Approval...');
    }
    if (error) {
      return h('div', { style: { padding: '24px', color: 'var(--destructive)' } }, 'Error: ' + error);
    }

    var approveRequired = getApproveRequiredTools();
    var matchableFields = getMatchableFields(newRule.tool);

    return h('div', { style: { padding: '24px', maxWidth: '900px', margin: '0 auto' } }, [
      // Header
      h('div', { style: { marginBottom: '24px' } }, [
        h('h1', { style: { fontSize: '24px', fontWeight: 'bold', marginBottom: '8px' } }, 'Runtime Approval'),
        h('p', { style: { opacity: '0.7', fontSize: '14px' } },
          'Runtime-enforced approval rules. The LLM cannot bypass these.')
      ]),

      // Default Policy (default_action selector)
      h(Card, { style: { marginBottom: '24px' } }, [
        h(CardContent, { style: { padding: '16px' } }, [
          h('h3', { style: { marginBottom: '12px', fontSize: '16px', fontWeight: '600' } }, 'Default Policy'),
          h('div', null, [
            h(Label, { style: { display: 'block', marginBottom: '4px' } }, 'Default Action (for tools not matched by any rule)'),
            h(Select, {
              value: defaultAction || 'none',
              onChange: function (e) {
                var val = e.target.value === 'none' ? null : e.target.value;
                saveDefaultAction(val);
              },
              style: { width: '100%' }
            }, [
              h(SelectOption, { value: 'none', key: 'none' }, 'None - let unmatched tools pass freely'),
              h(SelectOption, { value: 'approve', key: 'approve' }, 'Approve - prompt human for every unmatched tool'),
              h(SelectOption, { value: 'block', key: 'block' }, 'Block - deny every unmatched tool')
            ]),
            h('p', { style: { fontSize: '12px', opacity: '0.6', marginTop: '4px' } },
              'Covers new/unknown tools. Drag tools between the two columns below to manage trust.')
          ])
        ])
      ]),

      // Drag-and-drop: Approve Required vs Trusted
      h('div', { style: { display: 'flex', gap: '16px', marginBottom: '24px' } }, [
        // Left column: Approve Required
        h(Card, {
          style: { flex: '1', minHeight: '200px' },
          onDragOver: function (e) { e.preventDefault(); },
          onDrop: function (e) {
            e.preventDefault();
            var tool = e.dataTransfer.getData('text/plain');
            if (tool) dropToApproveRequired(tool);
            setDragTool(null);
          }
        }, [
          h(CardContent, { style: { padding: '12px' } }, [
            h('h3', { style: { fontSize: '14px', fontWeight: '600', marginBottom: '12px' } }, 'Runtime Approve Required'),
            h('p', { style: { fontSize: '11px', opacity: '0.5', marginBottom: '8px' } },
              approveRequired.length + ' tools'),
            h('div', { style: { display: 'flex', flexDirection: 'column', gap: '4px' } },
              approveRequired.length === 0
                ? h('p', { style: { opacity: '0.4', fontSize: '13px' } }, 'All tools are trusted.')
                : approveRequired.map(function (tool) {
                    return h('div', {
                      key: tool,
                      draggable: true,
                      onDragStart: function (e) {
                        e.dataTransfer.setData('text/plain', tool);
                        e.dataTransfer.effectAllowed = 'move';
                        setDragTool(tool);
                      },
                      onDragEnd: function () { setDragTool(null); },
                      style: {
                        padding: '6px 10px',
                        borderRadius: '6px',
                        border: '1px solid var(--border)',
                        cursor: 'grab',
                        opacity: dragTool === tool ? '0.4' : '1',
                        fontSize: '13px'
                      }
                    }, h(Badge, { variant: 'outline' }, tool));
                  })
            )
          ])
        ]),

        // Right column: Trusted (exempt)
        h(Card, {
          style: { flex: '1', minHeight: '200px' },
          onDragOver: function (e) { e.preventDefault(); },
          onDrop: function (e) {
            e.preventDefault();
            var tool = e.dataTransfer.getData('text/plain');
            if (tool) dropToTrusted(tool);
            setDragTool(null);
          }
        }, [
          h(CardContent, { style: { padding: '12px' } }, [
            h('h3', { style: { fontSize: '14px', fontWeight: '600', marginBottom: '12px' } }, 'Trusted (Exempt)'),
            h('p', { style: { fontSize: '11px', opacity: '0.5', marginBottom: '8px' } },
              exemptTools.length + ' tools'),
            h('div', { style: { display: 'flex', flexDirection: 'column', gap: '4px' } },
              exemptTools.length === 0
                ? h('p', { style: { opacity: '0.4', fontSize: '13px' } }, 'No trusted tools. Drag here to exempt.')
                : exemptTools.map(function (tool) {
                    return h('div', {
                      key: tool,
                      draggable: true,
                      onDragStart: function (e) {
                        e.dataTransfer.setData('text/plain', tool);
                        e.dataTransfer.effectAllowed = 'move';
                        setDragTool(tool);
                      },
                      onDragEnd: function () { setDragTool(null); },
                      style: {
                        padding: '6px 10px',
                        borderRadius: '6px',
                        border: '1px solid var(--border)',
                        cursor: 'grab',
                        opacity: dragTool === tool ? '0.4' : '1',
                        fontSize: '13px'
                      }
                    }, h(Badge, { variant: 'outline' }, tool));
                  })
            )
          ])
        ])
      ]),

      // Active Rules
      h(Card, { style: { marginBottom: '24px' } }, [
        h(CardContent, { style: { padding: '16px' } }, [
          h('h3', { style: { marginBottom: '16px', fontSize: '16px', fontWeight: '600' } }, 'Custom Rules'),
          rules.length === 0
            ? h('p', { style: { opacity: '0.6', fontSize: '14px' } }, 'No custom rules configured.')
            : h('div', { style: { display: 'flex', flexDirection: 'column', gap: '8px' } },
                rules.map(function (rule, idx) {
                  return h('div', {
                    key: idx,
                    style: {
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      padding: '12px', borderRadius: '8px', border: '1px solid var(--border)'
                    }
                  }, [
                    h('div', { style: { display: 'flex', flexDirection: 'column', gap: '4px' } }, [
                      h('div', { style: { display: 'flex', gap: '8px', alignItems: 'center' } }, [
                        h(Badge, { variant: 'outline' }, rule.tool),
                        h(Badge, { variant: rule.action === 'approve' ? 'outline' : 'destructive' },
                          rule.action === 'approve' ? 'Approve' : 'Block'),
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
          // Tool dropdown (dynamic from /api/tools/toolsets)
          h('div', { style: { marginBottom: '16px' } }, [
            h(Label, { style: { display: 'block', marginBottom: '4px' } }, 'Tool'),
            h(Select, {
              value: newRule.tool,
              onChange: function (e) { setNewRule(Object.assign({}, newRule, { tool: e.target.value })); },
              style: { width: '100%' }
            }, [
              h(SelectOption, { value: '', key: '__none' }, 'Select a tool...'),
              allTools.map(function (tool) {
                return h(SelectOption, { value: tool, key: tool }, tool);
              })
            ])
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
              ? h('p', { style: { opacity: '0.5', fontSize: '13px' } },
                  newRule.tool
                    ? 'No matchable fields known for this tool. Fields will be empty (matches any call).'
                    : 'Select a tool to see matchable fields.')
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
          h(Button, { onClick: addRule }, 'Add Rule')
        ])
      ]),

      // Info panel
      h('div', {
        style: {
          padding: '16px', borderRadius: '8px', border: '1px solid var(--border)',
          fontSize: '13px', opacity: '0.8'
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