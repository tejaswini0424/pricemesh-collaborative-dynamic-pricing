"""Optional MLflow mirror; database results remain authoritative."""
import logging
import os
log=logging.getLogger('pricemesh.tracking')

def mirror(job_id,kind,settings,result,folder):
    uri=os.getenv('MLFLOW_TRACKING_URI')
    if not uri: return {'status':'disabled'}
    try:
        import mlflow
        os.environ.setdefault('MLFLOW_HTTP_REQUEST_TIMEOUT','10')
        mlflow.set_tracking_uri(uri)
        mlflow.set_experiment('PriceMesh')
        with mlflow.start_run(run_name=f'{kind}-{job_id[:8]}') as run:
            mlflow.log_params({k:v for k,v in settings.items() if isinstance(v,(str,int,float,bool))})
            for index,row in enumerate(result.get('history',result.get('summary',[]))):
                mlflow.log_metrics({k:float(v) for k,v in row.items() if isinstance(v,(int,float)) and not isinstance(v,bool)},step=index)
            mlflow.log_artifacts(str(folder))
            return {'status':'synced','run_id':run.info.run_id}
    except Exception as exc:
        log.exception('MLflow mirror failed')
        return {'status':'failed','error':str(exc)[:300]}
