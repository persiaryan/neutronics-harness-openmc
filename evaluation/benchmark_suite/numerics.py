"""Unchanged Monte Carlo difference and practical-equivalence calculation."""
import math
from evaluation.scientific.records import require

def difference(a,b):
    delta=(a['mean']-b['mean'])*100000
    sigma=math.hypot(a['std_dev'],b['std_dev'])*100000
    require(math.isfinite(delta) and math.isfinite(sigma) and sigma>0,'Invalid numerical comparison')
    return {'delta_pcm':delta,'combined_sigma_pcm':sigma,'standardized_difference':delta/sigma}

def compare(a,b,margin=150.,multiplier=1.96):
    result=difference(a,b)
    bound=multiplier*result['combined_sigma_pcm']
    result['interval_pcm']=[result['delta_pcm']-bound,result['delta_pcm']+bound]
    result['margin_pcm']=margin
    result['status']=('agreement' if abs(result['delta_pcm'])+bound<=margin else
                      'resolved_discrepancy' if abs(result['delta_pcm'])-bound>margin else 'inconclusive')
    return result
