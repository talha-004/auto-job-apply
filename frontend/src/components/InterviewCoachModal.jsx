import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  BookOpen,
  Award,
  HelpCircle,
  Send,
  X,
  CheckCircle2,
  AlertCircle,
  Lightbulb,
  Building,
  Target
} from 'lucide-react';
import axios from 'axios';

const InterviewCoachModal = ({ isOpen, onClose, job }) => {
  const [prepData, setPrepData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('technical'); // technical, behavioral, dossier, practice

  // Practice state
  const [selectedQuestion, setSelectedQuestion] = useState('');
  const [practiceAnswer, setPracticeAnswer] = useState('');
  const [evaluating, setEvaluating] = useState(false);
  const [feedback, setFeedback] = useState(null);

  useEffect(() => {
    if (isOpen && job) {
      loadPrepPackage();
    } else {
      setPrepData(null);
      setFeedback(null);
    }
  }, [isOpen, job]);

  const loadPrepPackage = async () => {
    setLoading(true);
    try {
      const res = await axios.post('/api/interview-coach/generate', {
        job_id: job.id || job.application_id || 'preview_job',
        job_title: job.job_title || job.title || 'Software Engineer',
        company: job.company || 'Target Employer',
        job_description: job.job_description || job.description || ''
      });
      setPrepData(res.data);
      if (res.data.technical_questions?.length > 0) {
        setSelectedQuestion(res.data.technical_questions[0].question);
      }
    } catch (err) {
      console.error('Failed to load interview prep:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleEvaluateAnswer = async () => {
    if (!practiceAnswer.trim()) return;
    setEvaluating(true);
    try {
      const res = await axios.post('/api/interview-coach/practice/evaluate', {
        question: selectedQuestion,
        user_answer: practiceAnswer,
        expected_concepts: []
      });
      setFeedback(res.data);
    } catch (err) {
      console.error('Evaluation failed:', err);
    } finally {
      setEvaluating(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-4xl max-h-[90vh] bg-slate-900/95 border border-indigo-500/30 rounded-2xl shadow-2xl flex flex-col overflow-hidden text-slate-100">
        
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-gradient-to-r from-indigo-950/40 via-slate-900 to-purple-950/40">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 bg-indigo-500/10 border border-indigo-500/30 rounded-xl text-indigo-400">
              <Sparkles className="w-6 h-6 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="text-xl font-bold bg-gradient-to-r from-indigo-400 via-purple-300 to-pink-400 bg-clip-text text-transparent">
                  AI Interview Prep Coach
                </h3>
                <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                  Grounded in Fact Ledger
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Targeting: <span className="text-slate-200 font-medium">{job?.job_title || job?.title}</span> at <span className="text-indigo-400 font-semibold">{job?.company}</span>
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation Tabs */}
        <div className="flex px-6 pt-3 border-b border-slate-800 bg-slate-950/50 space-x-4">
          <button
            onClick={() => setActiveTab('technical')}
            className={`pb-3 text-sm font-medium flex items-center space-x-2 border-b-2 transition ${
              activeTab === 'technical'
                ? 'border-indigo-500 text-indigo-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <BookOpen className="w-4 h-4" />
            <span>Technical Deep-Dives ({prepData?.technical_questions?.length || 0})</span>
          </button>
          <button
            onClick={() => setActiveTab('behavioral')}
            className={`pb-3 text-sm font-medium flex items-center space-x-2 border-b-2 transition ${
              activeTab === 'behavioral'
                ? 'border-indigo-500 text-indigo-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Award className="w-4 h-4" />
            <span>STAR Behavioral Stories</span>
          </button>
          <button
            onClick={() => setActiveTab('dossier')}
            className={`pb-3 text-sm font-medium flex items-center space-x-2 border-b-2 transition ${
              activeTab === 'dossier'
                ? 'border-indigo-500 text-indigo-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Building className="w-4 h-4" />
            <span>Company Intelligence</span>
          </button>
          <button
            onClick={() => setActiveTab('practice')}
            className={`pb-3 text-sm font-medium flex items-center space-x-2 border-b-2 transition ${
              activeTab === 'practice'
                ? 'border-indigo-500 text-indigo-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Target className="w-4 h-4" />
            <span>Interactive Practice Studio</span>
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-20 space-y-3">
              <div className="w-10 h-10 border-4 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin" />
              <p className="text-sm text-slate-400">Synthesizing role requirements against verified candidate facts...</p>
            </div>
          ) : !prepData ? (
            <div className="text-center py-16 text-slate-400">
              <AlertCircle className="w-10 h-10 mx-auto mb-2 text-slate-500" />
              <p>Could not generate preparation dossier. Please try again.</p>
            </div>
          ) : (
            <>
              {/* Tab 1: Technical Questions */}
              {activeTab === 'technical' && (
                <div className="space-y-4">
                  {prepData.technical_questions?.map((q, idx) => (
                    <div
                      key={q.id || idx}
                      className="p-5 rounded-xl bg-slate-800/40 border border-slate-700/60 hover:border-indigo-500/40 transition space-y-3"
                    >
                      <div className="flex items-start justify-between">
                        <span className="text-xs font-semibold px-2.5 py-1 rounded-md bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                          {q.target_skill || 'Core Tech'} • {q.difficulty}
                        </span>
                        <button
                          onClick={() => {
                            setSelectedQuestion(q.question);
                            setActiveTab('practice');
                          }}
                          className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center space-x-1"
                        >
                          <span>Practice this</span>
                          <Send className="w-3 h-3" />
                        </button>
                      </div>
                      <h4 className="text-base font-semibold text-slate-100">{q.question}</h4>
                      <div className="flex flex-wrap gap-1.5">
                        {q.expected_concepts?.map((c, i) => (
                          <span key={i} className="text-xs px-2 py-0.5 rounded bg-slate-700/50 text-slate-300">
                            ✓ {c}
                          </span>
                        ))}
                      </div>
                      <div className="pt-2 text-xs text-slate-400 border-t border-slate-700/40">
                        <span className="font-medium text-slate-300">Suggested Approach: </span>
                        {q.sample_answer_outline}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Tab 2: STAR Stories */}
              {activeTab === 'behavioral' && (
                <div className="space-y-4">
                  {prepData.behavioral_stories?.map((story, idx) => (
                    <div
                      key={story.id || idx}
                      className="p-5 rounded-xl bg-slate-800/40 border border-slate-700/60 space-y-3"
                    >
                      <h4 className="text-base font-semibold text-indigo-300 flex items-center space-x-2">
                        <HelpCircle className="w-4 h-4 text-indigo-400" />
                        <span>"{story.prompt}"</span>
                      </h4>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                        <div className="p-3 bg-slate-900/60 rounded-lg border border-slate-800">
                          <span className="font-bold text-amber-400 block mb-1">📍 Situation</span>
                          <p className="text-slate-300">{story.situation}</p>
                        </div>
                        <div className="p-3 bg-slate-900/60 rounded-lg border border-slate-800">
                          <span className="font-bold text-blue-400 block mb-1">🎯 Task</span>
                          <p className="text-slate-300">{story.task}</p>
                        </div>
                        <div className="p-3 bg-slate-900/60 rounded-lg border border-slate-800">
                          <span className="font-bold text-purple-400 block mb-1">⚡ Action</span>
                          <p className="text-slate-300">{story.action}</p>
                        </div>
                        <div className="p-3 bg-slate-900/60 rounded-lg border border-slate-800">
                          <span className="font-bold text-emerald-400 block mb-1">📈 Result</span>
                          <p className="text-slate-300">{story.result}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Tab 3: Company Dossier */}
              {activeTab === 'dossier' && (
                <div className="space-y-6">
                  <div className="p-5 rounded-xl bg-slate-800/40 border border-slate-700/60 space-y-3">
                    <h4 className="text-sm font-semibold text-indigo-300 uppercase tracking-wider">
                      Strategic Focus Areas
                    </h4>
                    <div className="flex flex-wrap gap-2">
                      {prepData.dossier?.key_focus_areas?.map((area, i) => (
                        <span key={i} className="px-3 py-1.5 rounded-lg bg-indigo-950/40 border border-indigo-800/40 text-xs text-indigo-200">
                          {area}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="p-5 rounded-xl bg-slate-800/40 border border-slate-700/60 space-y-3">
                    <h4 className="text-sm font-semibold text-purple-300 uppercase tracking-wider flex items-center space-x-2">
                      <Lightbulb className="w-4 h-4 text-purple-400" />
                      <span>Reverse-Interview Questions to Ask the Hiring Team</span>
                    </h4>
                    <ul className="space-y-2 text-xs text-slate-300">
                      {prepData.dossier?.suggested_questions_to_ask?.map((q, i) => (
                        <li key={i} className="flex items-start space-x-2">
                          <span className="text-indigo-400 font-bold">•</span>
                          <span>{q}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}

              {/* Tab 4: Interactive Practice */}
              {activeTab === 'practice' && (
                <div className="space-y-5">
                  <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700">
                    <label className="block text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wider">
                      Target Interview Question
                    </label>
                    <input
                      type="text"
                      value={selectedQuestion}
                      onChange={(e) => setSelectedQuestion(e.target.value)}
                      placeholder="Enter or select question..."
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
                    />
                  </div>

                  <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700 space-y-3">
                    <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider">
                      Your Spoken / Written Response
                    </label>
                    <textarea
                      rows={5}
                      value={practiceAnswer}
                      onChange={(e) => setPracticeAnswer(e.target.value)}
                      placeholder="Outline your response using the STAR method or concrete system architecture trade-offs..."
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
                    />
                    <div className="flex justify-end">
                      <button
                        onClick={handleEvaluateAnswer}
                        disabled={evaluating || !practiceAnswer.trim()}
                        className="px-5 py-2.5 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white rounded-xl text-sm font-semibold flex items-center space-x-2 disabled:opacity-50 transition shadow-lg shadow-indigo-500/20"
                      >
                        {evaluating ? (
                          <>
                            <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                            <span>Evaluating...</span>
                          </>
                        ) : (
                          <>
                            <Sparkles className="w-4 h-4" />
                            <span>Evaluate Response</span>
                          </>
                        )}
                      </button>
                    </div>
                  </div>

                  {/* Feedback Panel */}
                  {feedback && (
                    <div className="p-5 rounded-xl bg-slate-900 border border-indigo-500/30 space-y-4 animate-in fade-in">
                      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                        <span className="text-sm font-bold text-slate-200">Evaluation Score</span>
                        <div className="flex items-center space-x-2">
                          <span className="text-2xl font-black bg-gradient-to-r from-indigo-400 to-pink-400 bg-clip-text text-transparent">
                            {feedback.score} / 10
                          </span>
                        </div>
                      </div>

                      <div className="space-y-2 text-xs">
                        <span className="font-semibold text-emerald-400 block">Key Strengths</span>
                        <ul className="space-y-1">
                          {feedback.strengths?.map((s, i) => (
                            <li key={i} className="flex items-center space-x-2 text-slate-300">
                              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
                              <span>{s}</span>
                            </li>
                          ))}
                        </ul>
                      </div>

                      <div className="space-y-2 text-xs">
                        <span className="font-semibold text-amber-400 block">Areas for Polish</span>
                        <ul className="space-y-1">
                          {feedback.improvement_areas?.map((imp, i) => (
                            <li key={i} className="flex items-center space-x-2 text-slate-300">
                              <AlertCircle className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" />
                              <span>{imp}</span>
                            </li>
                          ))}
                        </ul>
                      </div>

                      <div className="p-3 bg-indigo-950/30 border border-indigo-800/30 rounded-lg text-xs text-indigo-200">
                        <span className="font-bold text-indigo-300 block mb-1">Recommended Polish:</span>
                        {feedback.sample_polished_answer}
                      </div>
                    </div>
                  )}
                </>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-800 bg-slate-950 flex items-center justify-between text-xs text-slate-400">
          <span>AutoApplyJobs v3.0 Intelligent Career Agent</span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default InterviewCoachModal;
