
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Tuple, List, Dict, Any
import streamlit as st
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from datetime import datetime, timezone
import time

def get_contexts() -> Tuple[client.CoreV1Api, str]:
    try:
        config.load_kube_config()

    except Exception as e:
        try:
            config.load_incluster_config()

        except Exception as e2:
            print(f"Failed to load kube config: {e2}")

    core = client.CoreV1Api()

    try:
        contexts, active = config.list_kube_config_contexts()
        if active and 'context' in active:
            current_ns = active['context'].get('namespace', 'default')
    except Exception:
        current_ns = "default"
        pass
    return core, current_ns

def format_timedelta(ts: datetime) -> str:
	if ts is None:
		return "-"
	now = datetime.now(timezone.utc)
	diff = now - ts
	secs = int(diff.total_seconds())
	if secs < 60:
		return f"{secs}s"
	mins = secs // 60
	if mins < 60:
		return f"{mins}m"
	hours = mins // 60
	if hours < 24:
		return f"{hours}h"
	days = hours // 24
	return f"{days}d"


def main():

    try:
        core, namespace = get_contexts()
    except Exception as e:
        st.error(f"Failed to load Kubernetes configuration: {e}")
    
    st.set_page_config(page_title="K8s Pods Viewer", layout="wide")
    st.title(f"Kubernetes Pods for {namespace}")

    st.sidebar.title("Settings")

    if "auto_refresh" not in st.session_state:
        st.session_state.auto_refresh = True
        st.session_state.refresh_interval = 5

    auto_refresh = st.sidebar.toggle(
        "🔄 Auto-refresh", 
        value=st.session_state.auto_refresh,
        help="Activation of auto-refresh"
    )

    st.session_state.auto_refresh = auto_refresh

    if auto_refresh:
        refresh_interval = st.sidebar.number_input(
            "Refresh interval (secondes)",
            min_value=1,
            max_value=60,
            value=st.session_state.refresh_interval,
            step=2
        )
        st.session_state.refresh_interval = refresh_interval

    pods_list = []    
    pods = core.list_namespaced_pod(namespace)

    for pod in pods.items:
        status = pod.status
        meta = pod.metadata

        containers = status.container_statuses or []
        restarts = sum(c.restart_count for c in containers) if containers else 0
        started = getattr(status, "start_time", None) or getattr(meta, "creation_timestamp", None)

        pods_list.append({
            "name": meta.name,
            "namespace": meta.namespace,
            "node": getattr(status, "host_ip", "-"),
            "phase": getattr(status, "phase", "-"),
            "restarts": restarts,
            "age": format_timedelta(started) if started else "-",
        }) 

    st.dataframe(pods_list, use_container_width=True)

    if st.session_state.auto_refresh:
        time.sleep(st.session_state.refresh_interval)
        st.rerun()

if __name__ == "__main__":
    main()
