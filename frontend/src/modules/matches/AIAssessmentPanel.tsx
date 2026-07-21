import { TrendingUp, Target, Activity, Zap } from 'lucide-react';

export default function AIAssessmentPanel({ aiData, aiText }: { aiData: any, aiText: string }) {
  // 1. Skills Scorecard Data
  let skillsData: { subject: string, score: number }[] = [];
  if (aiData?.skills_scorecard && typeof aiData.skills_scorecard === 'object') {
    skillsData = Object.entries(aiData.skills_scorecard).map(([subject, score]) => {
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
        subject: subject.length > 20 ? subject.substring(0, 20) + '...' : subject, 
        score: numScore 
      };
    }).slice(0, 6);
  }
  
  if (skillsData.length === 0) {
    skillsData = [
      { subject: 'Skills', score: 50 },
      { subject: 'Experience', score: 50 },
      { subject: 'Culture Fit', score: 50 },
    ];
  }

  // 2. High-Impact Achievements
  let achievements = aiData?.high_impact_achievements || [];
  if (!Array.isArray(achievements) || achievements.length === 0) {
    if (aiData?.key_strengths && Array.isArray(aiData.key_strengths)) {
      achievements = aiData.key_strengths.slice(0, 3).map((s: string) => {
        const match = s.match(/\b\d+[%+xKMB]?\b/i);
        const metric = match ? match[0] : '★';
        const text = s.replace(metric, '').trim().substring(0, 50) + (s.length > 50 ? '...' : '');
        return { metric, text: text || s };
      });
    } else {
       achievements = [{ metric: '✓', text: 'Strong profile fit' }];
    }
  }

  // 3. Career Velocity
  const milestones = aiData?.career_velocity_milestones || [];

  // 4. Benchmarking
  const benchmark = aiData?.benchmarking_percentile || "Assessed";
  
  // 5. Working Persona
  const persona = aiData?.working_persona || null;

  return (
    <div className="flex flex-col gap-6 bg-[#0f0f11] rounded-2xl p-6 md:p-8 border border-zinc-800/80 shadow-2xl w-full overflow-hidden font-sans">
      
      {/* 1. Header (Badges only, no hook text) */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-2 border-b border-zinc-800/50">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-lg bg-orange-500/10 border border-orange-500/20 shadow-[0_0_15px_rgba(249,115,22,0.15)]">
            <Zap className="text-orange-400 shrink-0" size={20} />
          </div>
          <h3 className="text-xl font-bold text-zinc-100 tracking-tight">AI Assessment</h3>
        </div>
      </div>

      {/* Main Grid Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 min-w-0 pt-2">
        
        {/* Left Column: Skills Scorecard */}
        <div className="lg:col-span-5 flex flex-col gap-5 min-w-0">
          <div className="flex items-center gap-2">
            <Target className="text-zinc-500 shrink-0" size={18} />
            <h4 className="text-sm font-semibold text-zinc-400 uppercase tracking-widest">Skill Proficiency</h4>
          </div>
          
          <div className="flex flex-col gap-4 bg-zinc-900/40 p-6 rounded-xl border border-zinc-800/60 shadow-inner">
            {skillsData.map((skill, idx) => (
              <div key={idx} className="flex flex-col gap-1.5">
                <div className="flex justify-between items-end">
                  <span className="text-sm font-medium text-zinc-200">{skill.subject}</span>
                  <span className="text-xs font-bold text-zinc-500">{skill.score}%</span>
                </div>
                <div className="w-full h-2 bg-zinc-950 rounded-full overflow-hidden border border-zinc-800/50">
                  <div 
                    className="h-full rounded-full transition-all duration-1000 ease-out bg-gradient-to-r from-orange-600 to-orange-400"
                    style={{ width: `${skill.score}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right Column: Impact, Timeline, Persona */}
        <div className="lg:col-span-7 flex flex-col gap-8 min-w-0">
          
          {/* Key Impact Extracted */}
          <div className="flex flex-col gap-4">
            <div className="flex items-center gap-2">
              <TrendingUp className="text-zinc-500 shrink-0" size={18} />
              <h4 className="text-sm font-semibold text-zinc-400 uppercase tracking-widest">Key Impact Extracted</h4>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3 w-full">
              {achievements.map((ach: any, i: number) => (
                <div key={i} className="flex flex-col bg-zinc-900/40 rounded-xl p-5 border border-zinc-800/60 transition-colors hover:border-zinc-700/80 hover:bg-zinc-800/40 min-w-0">
                  <div className="text-3xl font-black text-transparent bg-clip-text bg-gradient-to-br from-emerald-400 to-emerald-600 mb-2 leading-none truncate" title={ach.metric}>
                    {ach.metric}
                  </div>
                  <div className="text-xs text-zinc-400 font-medium leading-relaxed whitespace-normal break-words line-clamp-3" title={ach.text}>
                    {ach.text}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-8">
            {/* Career Velocity Timeline */}
            {milestones.length > 0 && (
              <div className="flex flex-col gap-4">
                <div className="flex items-center gap-2">
                  <Activity className="text-zinc-500 shrink-0" size={18} />
                  <h4 className="text-sm font-semibold text-zinc-400 uppercase tracking-widest">Career Velocity</h4>
                </div>
                <div className="pl-3 border-l-2 border-zinc-800 space-y-5 py-1">
                  {milestones.map((m: any, i: number) => (
                    <div key={i} className="relative pl-5 group">
                      <div className="absolute -left-[23px] top-1.5 w-3 h-3 rounded-full bg-zinc-900 border-2 border-orange-500 shadow-[0_0_8px_rgba(249,115,22,0.4)] group-hover:bg-orange-500 transition-colors shrink-0" />
                      <div className="text-xs font-bold text-orange-500/80 mb-0.5">{m.year}</div>
                      <div className="text-sm text-zinc-300 font-medium leading-snug">{m.event}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {/* Culture Fit Fallback */}
            {(!persona || milestones.length === 0) && aiData?.culture_fit && (
              <div className="flex flex-col gap-4">
                <h4 className="text-sm font-semibold text-zinc-400 uppercase tracking-widest hidden sm:block opacity-0">Culture</h4>
                <div className="bg-zinc-900/40 p-5 rounded-xl border border-zinc-800/60 h-full">
                  <p className="text-sm text-zinc-300 leading-relaxed">{aiData.culture_fit}</p>
                </div>
              </div>
            )}
          </div>

        </div>
      </div>
      
      {/* Fallback to original text for details */}
      <div className="mt-4 pt-4 border-t border-zinc-800/50">
        <details className="text-sm text-zinc-500 group">
           <summary className="cursor-pointer hover:text-zinc-300 mb-2 font-medium transition-colors outline-none list-none flex items-center gap-2">
             <span className="w-4 h-4 flex items-center justify-center rounded bg-zinc-800 group-open:rotate-90 transition-transform">›</span>
             View Full AI Explanation
           </summary>
           <p className="whitespace-pre-wrap pl-6 border-l-2 border-zinc-800 mt-3 text-zinc-400 leading-relaxed font-mono text-xs">{aiText}</p>
        </details>
      </div>
    </div>
  );
}

