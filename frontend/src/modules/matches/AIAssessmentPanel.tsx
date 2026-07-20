import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer, Tooltip } from 'recharts';
import { TrendingUp, Target, Zap, Activity } from 'lucide-react';

export default function AIAssessmentPanel({ aiData, aiText }: { aiData: any, aiText: string }) {
  // 1. Radar Chart Data
  let radarData: any[] = [];
  if (aiData?.skills_scorecard && typeof aiData.skills_scorecard === 'object') {
    radarData = Object.entries(aiData.skills_scorecard).map(([subject, score]) => {
      let numScore = 0;
      if (typeof score === 'number') {
        numScore = score <= 10 ? score * 10 : score;
      } else if (typeof score === 'string') {
        const parsed = parseInt(score, 10);
        if (!isNaN(parsed)) {
          numScore = parsed <= 10 ? parsed * 10 : parsed;
        }
      }
      return { 
        subject: subject.length > 15 ? subject.substring(0, 15) + '...' : subject, 
        A: numScore, 
        B: 85, // Static ideal benchmark
        fullMark: 100 
      };
    }).slice(0, 6);
  }
  
  if (radarData.length === 0) {
    radarData = [
      { subject: 'Skills', A: 50, B: 85, fullMark: 100 },
      { subject: 'Experience', A: 50, B: 85, fullMark: 100 },
      { subject: 'Culture Fit', A: 50, B: 85, fullMark: 100 },
    ];
  }

  // 2. High-Impact Achievements
  let achievements = aiData?.high_impact_achievements || [];
  if (!Array.isArray(achievements) || achievements.length === 0) {
    if (aiData?.key_strengths && Array.isArray(aiData.key_strengths)) {
      achievements = aiData.key_strengths.slice(0, 2).map((s: string) => {
        const match = s.match(/\b\d+[%+xKMB]?\b/i);
        const metric = match ? match[0] : '★';
        const text = s.replace(metric, '').trim().substring(0, 40) + (s.length > 40 ? '...' : '');
        return { metric, text: text || s };
      });
    } else {
       achievements = [{ metric: '✓', text: 'Strong profile fit' }];
    }
  }

  // 3. Career Velocity
  const milestones = aiData?.career_velocity_milestones || [];

  // 4. The Hook & Benchmarking
  const hook = aiData?.hook_summary || (aiText ? aiText.split('.')[0] + '.' : "Candidate evaluation completed.");
  const benchmark = aiData?.benchmarking_percentile || "Assessed";
  
  // 5. Working Persona
  const persona = aiData?.working_persona || null;

  return (
    <div className="flex flex-col gap-6 bg-zinc-950/80 rounded-lg p-6 border border-zinc-800/80 shadow-inner w-full overflow-hidden">
      {/* 1. The Hook & Benchmarking */}
      <div className="border-b border-zinc-800/50 pb-5">
        <div className="flex flex-wrap items-center gap-3 mb-3">
          <div className="flex items-center gap-2">
            <Zap className="text-orange-500 shrink-0" size={20} />
            <h3 className="text-lg font-bold text-zinc-100 whitespace-nowrap">AI Assessment</h3>
          </div>
          
          <div className="flex flex-wrap gap-2 ml-auto">
            <span className="px-3 py-1 rounded bg-orange-500/10 text-orange-400 border border-orange-500/20 text-xs font-bold uppercase tracking-wider text-center break-words">
              {benchmark}
            </span>
            
            {aiData?.recommendation && (
              <span className={`px-3 py-1 rounded border text-xs font-bold uppercase tracking-wider text-center break-words ${
                String(aiData.recommendation).toLowerCase().includes('strong hire') ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' :
                String(aiData.recommendation).toLowerCase().includes('interview') ? 'bg-blue-500/10 text-blue-400 border-blue-500/20' :
                'bg-zinc-700/50 text-zinc-400 border-zinc-600'
              }`}>
                {aiData.recommendation}
              </span>
            )}
          </div>
        </div>
        <p className="text-xl font-medium text-zinc-300 italic whitespace-normal break-words leading-relaxed">"{hook}"</p>
      </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-10 min-w-0">
        {/* 2. Radar Chart */}
        <div className="lg:col-span-5 bg-zinc-900/50 rounded-xl p-5 border border-zinc-800/50 w-full overflow-hidden">
          <div className="flex items-center justify-center gap-2 mb-4">
            <Target className="text-orange-400 shrink-0" size={16} />
            <h4 className="text-sm font-semibold text-zinc-300 uppercase tracking-widest break-words text-center">Candidate vs Ideal Profile</h4>
          </div>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart cx="50%" cy="50%" outerRadius="70%" data={radarData}>
                <PolarGrid stroke="#3f3f46" />
                <PolarAngleAxis dataKey="subject" tick={{ fill: '#a1a1aa', fontSize: 12 }} />
                <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#18181b', borderColor: '#3f3f46', borderRadius: '8px' }}
                  itemStyle={{ color: '#e4e4e7' }}
                />
                <Radar name="Candidate" dataKey="A" stroke="#f97316" fill="#f97316" fillOpacity={0.3} />
                <Radar name="Ideal" dataKey="B" stroke="#10b981" fill="#10b981" fillOpacity={0.1} />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="lg:col-span-7 lg:pr-4 flex flex-col gap-6 min-w-0">
          {/* 3. High-Impact Achievements */}
          <div>
             <div className="flex items-center justify-center gap-2 mb-3">
              <TrendingUp className="text-emerald-400 shrink-0" size={16} />
              <h4 className="text-sm font-semibold text-zinc-300 uppercase tracking-widest break-words text-center">Key Impact Extracted</h4>
            </div>
            <div className="flex gap-4 w-full">
              {achievements.map((ach: any, i: number) => (
                <div key={i} className="flex-1 min-w-0 bg-zinc-900/50 rounded-xl p-4 border border-zinc-800/50 text-center flex flex-col justify-center">
                  <div className="text-lg lg:text-xl font-black text-orange-400 mb-2 line-clamp-2 leading-tight" title={ach.metric}>{ach.metric}</div>
                  <div className="text-[11px] lg:text-xs text-zinc-400 whitespace-normal line-clamp-3 leading-relaxed" title={ach.text}>{ach.text}</div>
                </div>
              ))}
            </div>
          </div>

          {/* 4. Career Velocity Timeline */}
          {milestones.length > 0 && (
            <div>
              <div className="flex items-center justify-center gap-2 mb-3">
                <Activity className="text-sky-400 shrink-0" size={16} />
                <h4 className="text-sm font-semibold text-zinc-300 uppercase tracking-widest break-words text-center">Career Velocity</h4>
              </div>
              <div className="pl-2 border-l border-zinc-700 space-y-4">
                {milestones.map((m: any, i: number) => (
                  <div key={i} className="relative pl-4">
                    <div className="absolute -left-[5px] top-1.5 w-2 h-2 rounded-full bg-orange-500 shadow-[0_0_8px_rgba(249,115,22,0.6)] shrink-0" />
                    <div className="text-[11px] lg:text-xs font-bold text-zinc-500">{m.year}</div>
                    <div className="text-[13px] lg:text-sm text-zinc-300 whitespace-normal line-clamp-2">{m.event}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
          
          {/* 5. Working Persona */}
          {persona && (
            <div className="mt-2">
              <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-widest mb-3 break-words text-center">Working Persona</h4>
              <div className="space-y-3">
                 <div className="flex items-center gap-3">
                    <span className="text-[10px] text-zinc-400 w-16 text-right shrink-0">Independent</span>
                    <div className="flex-1 h-1.5 bg-zinc-800 rounded-full relative min-w-0">
                      <div className="absolute top-1/2 -translate-y-1/2 w-3 h-3 bg-orange-400 rounded-full shadow-[0_0_5px_rgba(249,115,22,0.5)]" style={{ left: `calc(${persona.collaborative_score ?? 50}% - 6px)` }}></div>
                    </div>
                    <span className="text-[10px] text-zinc-400 w-16 shrink-0">Collaborative</span>
                 </div>
                 <div className="flex items-center gap-3">
                    <span className="text-[10px] text-zinc-400 w-16 text-right shrink-0">Intuitive</span>
                    <div className="flex-1 h-1.5 bg-zinc-800 rounded-full relative min-w-0">
                      <div className="absolute top-1/2 -translate-y-1/2 w-3 h-3 bg-orange-400 rounded-full shadow-[0_0_5px_rgba(249,115,22,0.5)]" style={{ left: `calc(${persona.analytical_score ?? 50}% - 6px)` }}></div>
                    </div>
                    <span className="text-[10px] text-zinc-400 w-16 shrink-0">Analytical</span>
                 </div>
              </div>
            </div>
          )}

          {/* 6. Culture Fit Summary (Fallback if no persona/milestones) */}
          {(!persona || milestones.length === 0) && aiData?.culture_fit && (
            <div>
              <div className="flex items-center justify-center gap-2 mb-3">
                <Activity className="text-sky-400 shrink-0" size={16} />
                <h4 className="text-sm font-semibold text-zinc-300 uppercase tracking-widest break-words text-center">Culture & Soft Skills</h4>
              </div>
              <div className="pl-4 border-l border-zinc-700 break-words">
                <div className="text-sm text-zinc-300 leading-relaxed whitespace-normal">{aiData.culture_fit}</div>
              </div>
            </div>
          )}
        </div>
      </div>
      
      {/* Fallback to original text for details */}
      <div className="mt-4 pt-4 border-t border-zinc-800/50">
        <details className="text-sm text-zinc-400">
           <summary className="cursor-pointer hover:text-zinc-300 mb-2">View Full AI Explanation</summary>
           <p className="whitespace-pre-wrap pl-4 border-l-2 border-zinc-800 mt-2 break-words whitespace-normal">{aiText}</p>
        </details>
      </div>
    </div>
  );
}
