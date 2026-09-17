import { useState } from 'react';
import PageWrapper from '../components/PageWrapper';
import { ShieldCheck, ArrowRight } from 'lucide-react';
import { grammar } from '../api';
import { useToast } from '../context/ToastContext';
import { ResultBox, Spinner, FormGroup } from '../components/ui';

export default function GrammarPage() {
  const [text, setText] = useState('');
  const [result, setResult] = useState('');
  const [loading, setLoading] = useState(false);
  const toast = useToast();

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!text.trim()) return;
    setLoading(true);
    setResult('');
    try {
      const { data } = await grammar(text);
      setResult(data.corrected_text);
      toast('Grammar check complete!', 'success');
    } catch (err) {
      toast(err.response?.data?.detail ?? 'Grammar check failed', 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <PageWrapper>
      <div className="page-header">
        <h1>Grammar Fix</h1>
        <p>Detect and correct grammatical errors powered by Qwen 2.5.</p>
      </div>

      <div className="card" style={{ maxWidth: 760 }}>
        <div className="card-header">
          <div className="card-icon" style={{ background: 'rgba(16,185,129,0.12)', color: 'var(--clr-success)' }}>
            <ShieldCheck size={20} />
          </div>
          <div>
            <div className="card-title">Grammar Checker</div>
            <div className="card-desc">Powered by a unified LLM — corrects grammar, punctuation, and spelling</div>
          </div>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <FormGroup label="Input Text">
            <textarea
              id="grammar-input"
              className="input"
              placeholder="Type or paste text to check…"
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={5}
            />
          </FormGroup>
          <div style={{ display: 'flex', gap: 10 }}>
            <button id="grammar-submit-btn" className="btn btn-primary" type="submit" disabled={loading || !text.trim()}>
              {loading ? <Spinner /> : <ArrowRight size={16} />}
              {loading ? 'Checking…' : 'Check Grammar'}
            </button>
            <button className="btn btn-secondary" type="button" onClick={() => { setText(''); setResult(''); }}>
              Clear
            </button>
          </div>
        </form>

        {result && (
          <div className="mt-4">
            <div className="form-label mb-2">Corrected Text</div>
            <ResultBox text={result} />
          </div>
        )}
      </div>
    </PageWrapper>
  );
}
