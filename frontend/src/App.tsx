import { useState, useEffect, useCallback } from 'react';
import { ReactFlowProvider } from '@xyflow/react';
import { ScenarioList } from './components/ScenarioList';
import { FlowEditor } from './components/FlowEditor';
import { api } from './api/client';
import type { ScenarioListItem } from './types';

export default function App() {
  const [scenarios, setScenarios] = useState<ScenarioListItem[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [selectedName, setSelectedName] = useState('');
  const [twilioPhone, setTwilioPhone] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    api.listScenarios().then(setScenarios).catch((e) => setError(`API接続エラー: ${e.message}`));
  }, []);

  const handleSelect = useCallback(async (id: number) => {
    setSelectedId(id);
    const scenario = await api.getScenario(id);
    setSelectedName(scenario.name);
    setTwilioPhone(scenario.twilio_phone_number || '');
  }, []);

  const handleCreate = useCallback(async (name: string) => {
    setError('');
    try {
      const created = await api.createScenario({ name });
      setScenarios((prev) => [
        {
          id: created.id,
          name: created.name,
          description: created.description,
          created_at: created.created_at,
          updated_at: created.updated_at,
        },
        ...prev,
      ]);
      setSelectedId(created.id);
      setSelectedName(created.name);
      setTwilioPhone('');
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(`シナリオ作成エラー: ${msg}`);
    }
  }, []);

  const handleDelete = useCallback(
    async (id: number) => {
      setError('');
      try {
        await api.deleteScenario(id);
        setScenarios((prev) => prev.filter((s) => s.id !== id));
        if (selectedId === id) {
          setSelectedId(null);
          setSelectedName('');
          setTwilioPhone('');
        }
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        setError(`削除エラー: ${msg}`);
      }
    },
    [selectedId],
  );

  const handlePhoneUpdate = useCallback(
    async (phone: string) => {
      setTwilioPhone(phone);
      if (selectedId) {
        await api.updateScenario(selectedId, {
          twilio_phone_number: phone,
        });
      }
    },
    [selectedId],
  );

  return (
    <div style={{ display: 'flex', height: '100vh', fontFamily: 'system-ui, sans-serif' }}>
      {error && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            zIndex: 100,
            background: '#fef2f2',
            color: '#991b1b',
            padding: '10px 16px',
            fontSize: 13,
            borderBottom: '1px solid #fecaca',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <span>{error}</span>
          <button
            onClick={() => setError('')}
            style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 16, color: '#991b1b' }}
          >
            ×
          </button>
        </div>
      )}
      <ScenarioList
        scenarios={scenarios}
        selectedId={selectedId}
        onSelect={handleSelect}
        onCreate={handleCreate}
        onDelete={handleDelete}
      />
      <ReactFlowProvider>
        {selectedId ? (
          <FlowEditor
            scenarioId={selectedId}
            scenarioName={selectedName}
            onPhoneUpdate={handlePhoneUpdate}
            twilioPhone={twilioPhone}
          />
        ) : (
          <div
            style={{
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#9ca3af',
              fontSize: 15,
            }}
          >
            シナリオを選択または作成してください
          </div>
        )}
      </ReactFlowProvider>
    </div>
  );
}
