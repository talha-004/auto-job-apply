import React, { useState, useEffect } from 'react';
import { 
  TrendingUp, 
  Award, 
  Send, 
  Calendar, 
  CheckCircle, 
  RefreshCw, 
  Clock, 
  BarChart3, 
  ExternalLink,
  ChevronRight,
  Filter
} from 'lucide-react';
import { analyticsAPI, followupAPI } from '../services/api';

export function ConversionFunnel() {
  const [funnel, setFunnel] = useState(null);
  const [roi, setRoi] = useState([]);
  const [summary, setSummary] = useState(null);
  const [followups, setFollowups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [approvingId, setApprovingId] = useState(null);
  const [feedback, setFeedback] = useState(null);

  const loadAllAnalytics = async () => {
    setLoading(true);
    try {
      const [fData, roiData, sumData, followData] = await Promise.all([
        analyticsAPI.getFunnel().catch(() => null),
        analyticsAPI.getPlatformROI().catch(() => ({ platforms: [] })),
        analyticsAPI.getSummary().catch(() => null),
        followupAPI.getPending(5).catch(() => ({ followups: [] }))
      ]);

      if (fData) setFunnel(fData);
      if (roiData?.platforms) setRoi(roiData.platforms);
      if (sumData) setSummary(sumData);
      if (followData?.followups) setFollowups(followData.followups);
    } catch (err) {
      console.error('Failed to load conversion analytics:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAllAnalytics();
  }, []);

  const handleApproveFollowup = async (appId) => {
    setApprovingId(appId);
    try {
      await followupAPI.approve(appId);
      setFeedback({ msg: 'Follow-up email approved and dispatched!', type: 'success' });
      setFollowups(prev => prev.filter(f => f.application_id !== appId));
    } catch (err) {
      setFeedback({ msg: 'Failed to approve follow-up: Daily cap reached or error.', type: 'error' });
    } finally {
      setApprovingId(null);
      setTimeout(() => setFeedback(null), 4000);
    }
  };

  return (
    <div className="space-y-8 animate-fade-in text-slate-100">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <TrendingUp className="w-7 h-7 text-indigo-400" />
            Conversion Funnel & Performance Analytics
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            Real-time pipeline tracking, multi-platform ROI, and automated 5-day recruiter follow-up management.
          </p>
        </div>
        <button
          onClick={loadAllAnalytics}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium rounded-lg border border-slate-700 transition"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh Metrics
        </button>
      </div>

      {feedback && (
        <div className={`p-4 rounded-lg border text-sm flex items-center gap-2 ${
          feedback.type === 'success' 
            ? 'bg-emerald-950/40 border-emerald-800 text-emerald-300' 
            : 'bg-rose-950/40 border-rose-800 text-rose-300'
        }`}>
          <CheckCircle className="w-5 h-5 flex-shrink-0" />
          <span>{feedback.msg}</span>
        </div>
      )}

      {/* KPI Overview Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-slate-900/60 border border-slate-800 p-5 rounded-xl backdrop-blur-sm">
          <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider">
            Total Applications
            <Send className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-bold text-white">{summary?.total_applications ?? 0}</span>
            <span className="text-xs text-indigo-400 font-medium">Submitted</span>
          </div>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 p-5 rounded-xl backdrop-blur-sm">
          <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider">
            Interviews Scheduled
            <Calendar className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-bold text-white">{summary?.interviews_scheduled ?? 0}</span>
            <span className="text-xs text-emerald-400 font-medium">Callbacks</span>
          </div>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 p-5 rounded-xl backdrop-blur-sm">
          <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider">
            Interview Rate
            <TrendingUp className="w-4 h-4 text-amber-400" />
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-bold text-white">{summary?.interview_rate_pct ?? 0}%</span>
            <span className="text-xs text-amber-400 font-medium">Applied-to-Interview</span>
          </div>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 p-5 rounded-xl backdrop-blur-sm">
          <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider">
            Top Performing Channel
            <Award className="w-4 h-4 text-purple-400" />
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-white truncate">{summary?.top_performing_platform ?? 'LinkedIn'}</span>
          </div>
        </div>
      </div>

      {/* Main Grid: Visual Funnel & Platform ROI */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Stage-by-Stage Visual Funnel */}
        <div className="lg:col-span-2 bg-slate-900/60 border border-slate-800 rounded-xl p-6 backdrop-blur-sm">
          <h3 className="text-lg font-bold text-white flex items-center gap-2 mb-6">
            <BarChart3 className="w-5 h-5 text-indigo-400" />
            Stage-by-Stage Pipeline Funnel
          </h3>

          <div className="space-y-5">
            {funnel?.stages?.map((stage, idx) => (
              <div key={idx} className="space-y-1.5">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-semibold text-slate-200">{stage.stage}</span>
                  <div className="flex items-center gap-3 text-xs">
                    <span className="text-slate-400 font-mono">{stage.count} items</span>
                    <span className="px-2 py-0.5 rounded-full bg-slate-800 text-indigo-300 border border-slate-700 font-mono">
                      {stage.conversion_from_previous_pct}% from prev
                    </span>
                  </div>
                </div>
                <div className="w-full bg-slate-800 rounded-full h-3.5 overflow-hidden">
                  <div 
                    className="h-full rounded-full transition-all duration-700 bg-gradient-to-r from-indigo-500 via-purple-500 to-emerald-400"
                    style={{ width: `${Math.max(4, stage.conversion_from_top_pct)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Platform ROI Cards */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 backdrop-blur-sm flex flex-col justify-between">
          <div>
            <h3 className="text-lg font-bold text-white flex items-center gap-2 mb-4">
              <Filter className="w-5 h-5 text-emerald-400" />
              Platform ROI Breakdown
            </h3>
            <p className="text-xs text-slate-400 mb-5">
              Comparative volume and conversion efficacy across active job discovery providers.
            </p>

            <div className="space-y-4">
              {roi.map((p, idx) => (
                <div key={idx} className="bg-slate-800/50 border border-slate-700/60 rounded-lg p-3.5 flex items-center justify-between">
                  <div>
                    <div className="font-bold text-white text-sm">{p.platform}</div>
                    <div className="text-xs text-slate-400 mt-0.5">
                      {p.applications_count} applied • {p.interviews_count} interviews
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-bold text-emerald-400">{p.conversion_rate_pct}%</div>
                    <div className="text-[10px] text-slate-400 uppercase tracking-wider">Conversion</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Recruiter 5-Day Follow-Up Center */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 backdrop-blur-sm">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <Clock className="w-5 h-5 text-amber-400" />
              Automated 5-Day Follow-Up Queue
            </h3>
            <p className="text-xs text-slate-400 mt-1">
              Applications submitted $\ge$ 5 business days ago with no response. Send a polite 3-sentence check-in to boost interview callbacks.
            </p>
          </div>
          <span className="text-xs font-mono px-3 py-1 bg-amber-950/40 text-amber-300 border border-amber-800/60 rounded-full">
            {followups.length} Eligible
          </span>
        </div>

        {followups.length === 0 ? (
          <div className="text-center py-8 border border-dashed border-slate-800 rounded-lg text-slate-400 text-sm">
            <CheckCircle className="w-8 h-8 text-emerald-500 mx-auto mb-2 opacity-70" />
            No applications currently pending follow-up. All applications under 5 days old or already checked in.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {followups.map((item, idx) => (
              <div key={idx} className="bg-slate-800/40 border border-slate-700/60 rounded-xl p-4 flex flex-col justify-between space-y-3">
                <div>
                  <div className="flex items-center justify-between">
                    <h4 className="font-bold text-white text-sm">{item.job_title}</h4>
                    <span className="text-xs text-amber-400 font-mono">{item.days_elapsed} days ago</span>
                  </div>
                  <div className="text-xs text-slate-300 font-medium">{item.company}</div>
                  <div className="text-[11px] text-slate-400 mt-1 truncate">To: {item.recommended_recipient}</div>
                  <div className="mt-3 p-2.5 bg-slate-900/80 rounded border border-slate-800 text-xs text-slate-300 font-mono whitespace-pre-wrap line-clamp-3">
                    {item.draft_body}
                  </div>
                </div>

                <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
                  <button
                    onClick={() => handleApproveFollowup(item.application_id)}
                    disabled={approvingId === item.application_id}
                    className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold rounded-lg flex items-center gap-1.5 transition"
                  >
                    <Send className="w-3.5 h-3.5" />
                    {approvingId === item.application_id ? 'Dispatching...' : 'Approve & Send Follow-Up'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
export default ConversionFunnel;
