/* ============================================================
   DroneMap — UI Controller (Simplified & Accessible)
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {
  console.log('[dronemap] UI Controller initialized');

  // Prevent default browser drag/drop navigation
  window.addEventListener('dragover', (e) => e.preventDefault(), false);
  window.addEventListener('drop', (e) => e.preventDefault(), false);

  // UI Element Selectors
  const btnOpenUpload    = document.getElementById('btn-open-upload');
  const uploadModal      = document.getElementById('upload-modal');
  const btnModalClose    = document.getElementById('btn-modal-close');
  const btnCancelUpload  = document.getElementById('btn-cancel-upload');
  const uploadForm       = document.getElementById('upload-form');

  const jobModal         = document.getElementById('job-modal');
  const btnJobClose      = document.getElementById('btn-job-modal-close');
  const jobProgressBar   = document.getElementById('job-progress-bar');
  const jobLogOutput     = document.getElementById('job-log-output');
  const jobElapsedTime   = document.getElementById('job-elapsed-time');
  const jobModalFooter   = document.getElementById('job-modal-footer');
  const btnViewFinished  = document.getElementById('btn-view-finished-model');

  const runListContainer = document.getElementById('run-list');
  const btnRefreshRuns   = document.getElementById('btn-refresh-runs');
  const reportSection    = document.getElementById('report-section');
  const accuracyReportEl = document.getElementById('accuracy-report');
  const downloadSection  = document.getElementById('download-section');
  const downloadLinksEl  = document.getElementById('download-links');

  // Modal Open & Close Handlers
  if (btnOpenUpload) {
    btnOpenUpload.addEventListener('click', (e) => {
      e.preventDefault();
      uploadModal.style.display = 'flex';
      
      const d = new Date();
      const pad = (n) => String(n).padStart(2, '0');
      const inputRunId = document.getElementById('input-run-id');
      if (inputRunId && !inputRunId.value) {
        inputRunId.placeholder = `flight_${d.getFullYear()}${pad(d.getMonth()+1)}${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}`;
      }
    });
  }

  function closeUploadModal() {
    uploadModal.style.display = 'none';
  }

  if (btnModalClose) btnModalClose.addEventListener('click', closeUploadModal);
  if (btnCancelUpload) btnCancelUpload.addEventListener('click', closeUploadModal);
  if (btnJobClose) btnJobClose.addEventListener('click', () => { jobModal.style.display = 'none'; });

  window.addEventListener('click', (e) => {
    if (e.target === uploadModal) closeUploadModal();
    if (e.target === jobModal && btnJobClose.style.display !== 'none') {
      jobModal.style.display = 'none';
    }
  });

  // Drag & Drop Setup
  function setupDropzone(dropzoneId, inputId, infoBoxId) {
    const dropzone = document.getElementById(dropzoneId);
    const input = document.getElementById(inputId);
    const infoBox = document.getElementById(infoBoxId);
    if (!dropzone || !input || !infoBox) return;

    const dropContent = dropzone.querySelector('.dropzone-content');

    ['dragenter', 'dragover'].forEach(eventName => {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (!dropzone.classList.contains('dropzone-disabled')) {
          dropzone.classList.add('drag-over');
        }
      }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.remove('drag-over');
      }, false);
    });

    dropzone.addEventListener('drop', (e) => {
      if (dropzone.classList.contains('dropzone-disabled')) return;
      const files = e.dataTransfer.files;
      if (files && files.length > 0) {
        input.files = files;
        updateFileInfo(files[0]);
      }
    }, false);

    input.addEventListener('change', () => {
      if (input.files && input.files.length > 0) {
        updateFileInfo(input.files[0]);
      }
    });

    function updateFileInfo(file) {
      if (dropContent) dropContent.style.display = 'none';
      infoBox.style.display = 'flex';
      const nameEl = infoBox.querySelector('.file-name');
      const sizeEl = infoBox.querySelector('.file-size');
      if (nameEl) nameEl.textContent = file.name;
      if (sizeEl) sizeEl.textContent = `(${(file.size / 1024 / 1024).toFixed(1)} MB)`;
    }

    const clearBtn = infoBox.querySelector('.btn-clear-file');
    if (clearBtn) {
      clearBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        input.value = '';
        infoBox.style.display = 'none';
        if (dropContent) dropContent.style.display = 'flex';
      });
    }
  }

  setupDropzone('video-dropzone', 'video-file-input', 'video-file-info');
  setupDropzone('telem-dropzone', 'telem-file-input', 'telem-file-info');

  // No-telemetry checkbox toggle
  const chkNoTelem = document.getElementById('chk-no-telemetry');
  const telemDropzone = document.getElementById('telem-dropzone');
  const telemInput = document.getElementById('telem-file-input');

  if (chkNoTelem && telemDropzone) {
    chkNoTelem.addEventListener('change', (e) => {
      if (e.target.checked) {
        telemDropzone.classList.add('dropzone-disabled');
        if (telemInput) telemInput.disabled = true;
      } else {
        telemDropzone.classList.remove('dropzone-disabled');
        if (telemInput) telemInput.disabled = false;
      }
    });
  }

  // Upload & Process Submission
  if (uploadForm) {
    uploadForm.addEventListener('submit', (e) => {
      e.preventDefault();

      const videoInput = document.getElementById('video-file-input');
      if (!videoInput.files || videoInput.files.length === 0) {
        alert('Please select a drone video file to proceed.');
        return;
      }

      const formData = new FormData(uploadForm);
      uploadModal.style.display = 'none';
      jobModal.style.display = 'flex';

      // Reset Stepper & Logs
      document.querySelectorAll('.step-card').forEach(c => {
        c.className = 'step-card';
        const st = c.querySelector('.step-status');
        if (st) st.textContent = 'Pending';
      });
      jobProgressBar.style.width = '0%';
      jobLogOutput.textContent = 'Uploading drone video to processing server…\n';
      jobModalFooter.style.display = 'none';
      btnJobClose.style.display = 'none';
      document.getElementById('job-modal-title').textContent = 'Processing Video…';
      document.getElementById('job-modal-subtitle').textContent = 'Building 3D model from flight video';

      const startTime = Date.now();
      const timerInterval = setInterval(() => {
        const elapsed = Math.floor((Date.now() - startTime) / 1000);
        const m = String(Math.floor(elapsed / 60)).padStart(2, '0');
        const s = String(elapsed % 60).padStart(2, '0');
        jobElapsedTime.textContent = `${m}:${s}`;
      }, 1000);

      // XHR upload for real-time progress
      const xhr = new XMLHttpRequest();
      xhr.open('POST', '/api/jobs');

      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) {
          const pct = Math.round((event.loaded / event.total) * 100);
          jobProgressBar.style.width = `${Math.min(pct, 95)}%`;
          jobLogOutput.textContent = `Uploading video: ${pct}% (${(event.loaded/1024/1024).toFixed(1)} MB / ${(event.total/1024/1024).toFixed(1)} MB)…\n`;
        }
      };

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          const data = JSON.parse(xhr.responseText);
          const jobId = data.job_id;
          const runId = data.run_id;
          startJobPolling(jobId, runId, timerInterval);
        } else {
          clearInterval(timerInterval);
          btnJobClose.style.display = 'block';
          document.getElementById('job-modal-title').textContent = 'Upload Failed';
          jobLogOutput.textContent += `\nError: Server returned status ${xhr.status} — ${xhr.responseText}`;
        }
      };

      xhr.onerror = () => {
        clearInterval(timerInterval);
        btnJobClose.style.display = 'block';
        document.getElementById('job-modal-title').textContent = 'Network Error';
        jobLogOutput.textContent += '\nNetwork error occurred while uploading video.';
      };

      xhr.send(formData);
    });
  }

  // Job Polling
  function startJobPolling(jobId, runId, timerInterval) {
    const stageOrder = ['frames', 'masks', 'pose', 'dense', 'mesh', 'export'];

    const pollInterval = setInterval(async () => {
      try {
        const res = await fetch(`/api/jobs/${jobId}`);
        if (!res.ok) return;
        const job = await res.json();

        // Update logs
        if (job.logs && job.logs.length) {
          jobLogOutput.textContent = job.logs.join('\n');
          jobLogOutput.scrollTop = jobLogOutput.scrollHeight;
        }

        // Update Stepper Cards
        let completedCount = 0;
        stageOrder.forEach(stKey => {
          const card = document.querySelector(`.step-card[data-stage="${stKey}"]`);
          if (!card) return;
          const status = job.stages[stKey];
          const stEl = card.querySelector('.step-status');

          card.classList.remove('active', 'completed', 'failed');
          if (status === 'ok') {
            card.classList.add('completed');
            if (stEl) stEl.textContent = 'Done';
            completedCount++;
          } else if (status === 'running') {
            card.classList.add('active');
            if (stEl) stEl.textContent = 'Processing';
          } else if (status === 'failed') {
            card.classList.add('failed');
            if (stEl) stEl.textContent = 'Failed';
          } else {
            if (stEl) stEl.textContent = 'Pending';
          }
        });

        // Progress bar
        const progressPercent = Math.max(10, Math.round((completedCount / stageOrder.length) * 100));
        jobProgressBar.style.width = `${progressPercent}%`;

        // Completion
        if (job.status === 'completed') {
          clearInterval(pollInterval);
          clearInterval(timerInterval);
          jobProgressBar.style.width = '100%';
          jobModalFooter.style.display = 'flex';
          btnJobClose.style.display = 'block';
          document.getElementById('job-modal-title').textContent = 'Processing Complete!';
          document.getElementById('job-modal-subtitle').textContent = `3D model ready for '${runId}'`;

          btnViewFinished.onclick = () => {
            jobModal.style.display = 'none';
            selectRun(runId, true);
            fetchRuns(runId);
          };

          fetchRuns(runId);
        } else if (job.status === 'failed') {
          clearInterval(pollInterval);
          clearInterval(timerInterval);
          btnJobClose.style.display = 'block';
          document.getElementById('job-modal-title').textContent = 'Processing Error';
          document.getElementById('job-modal-subtitle').textContent = job.error || 'A processing step failed.';
        }
      } catch (err) {
        console.error('[dronemap] Poll error:', err);
      }
    }, 1200);
  }

  // Centralized Run Selection & Viewer Synchronization
  function selectRun(runId, hasModel = true) {
    window.currentRunId = runId;
    document.querySelectorAll('.run-card').forEach(c => {
      c.classList.toggle('selected', c.dataset.runId === runId);
    });
    if (hasModel) {
      if (window.load3DModel) {
        window.load3DModel(runId);
      } else {
        window.pendingRunId = runId;
      }
    }
    showTextureVariantToggle(runId);
    loadAccuracyReport(runId);
    renderDownloadLinks(runId);
  }
  window.selectRun = selectRun;

  // The texture-variant toggle exists only for runs that actually produced two
  // atlases. Offering it unconditionally would give a button that 404s, which
  // is worse than not offering it at all.
  async function showTextureVariantToggle(runId) {
    const grp = document.getElementById('grp-texture-variant');
    const div = document.getElementById('div-texture-variant');
    const show = (on) => {
      if (grp) grp.style.display = on ? '' : 'none';
      if (div) div.style.display = on ? '' : 'none';
    };
    show(false);
    try {
      const res = await fetch(`/api/runs/${runId}/model_alt.glb`, { method: 'HEAD' });
      if (!res.ok || window.currentRunId !== runId) return;
      const label = await textureVariantLabel(runId);
      const btnAlt = document.getElementById('btn-variant-alt');
      const btnPrimary = document.getElementById('btn-variant-primary');
      if (btnAlt && label) {
        btnAlt.textContent = label.alt;
        btnAlt.title = label.altTitle;
      }
      if (btnPrimary && label) {
        btnPrimary.textContent = label.primary;
        btnPrimary.title = label.primaryTitle;
      }
      show(true);
    } catch (err) {
      /* No alternate variant for this run; the toggle stays hidden. */
    }
  }

  // Name the two buttons after what actually differs, read from the manifest,
  // so the comparison is legible without knowing the pipeline internals.
  async function textureVariantLabel(runId) {
    try {
      const res = await fetch(`/api/runs/${runId}`);
      const m = await res.json();
      const outs = ((m.stages || {}).mesh || {}).outputs || {};
      const which = outs.textured_obj_alt_label;
      if (which === 'seam_levelled') {
        return {
          primary: 'No Seam Levelling',
          primaryTitle: 'Raw per-view projection — true colour, visible seams',
          alt: 'Seam Levelled',
          altTitle: 'OpenMVS blended atlas — the variant that came out dark',
        };
      }
      return {
        primary: 'Seam Levelled',
        primaryTitle: 'OpenMVS blended atlas (adopted)',
        alt: 'No Seam Levelling',
        altTitle: 'Raw per-view projection — true colour, visible seams',
      };
    } catch (err) {
      return null;
    }
  }

  // Listen for when 3D viewer finishes module initialization
  window.addEventListener('viewer-ready', () => {
    if (window.currentRunId && window.load3DModel) {
      window.load3DModel(window.currentRunId);
      showTextureVariantToggle(window.currentRunId);
    }
  });

  // Sidebar Runs List & Reports
  async function fetchRuns(preferredRunId = null) {
    try {
      const res = await fetch('/api/runs');
      const runs = await res.json();
      if (!runs || !runs.length) {
        runListContainer.innerHTML = '<div class="empty-state">No projects yet. Click <strong>+ Process Drone Video</strong> above to start.</div>';
        return;
      }

      runListContainer.innerHTML = '';
      let autoSelected = false;
      const targetId = preferredRunId || window.currentRunId;

      runs.forEach((run) => {
        const card = document.createElement('div');
        const isTarget = targetId ? run.run_id === targetId : false;
        card.className = `run-card ${isTarget ? 'selected' : ''}`;
        card.dataset.runId = run.run_id;
        const dateStr = run.created_utc ? run.created_utc.substring(0, 10) : 'Recent';
        // 'georeferenced' shares the caution colour with 'relative': the model
        // carries world coordinates but their error was never measured, so it
        // must not look as trustworthy as a validated run.
        const badgeClass = run.status_type === 'validated' ? 'badge-ready' :
                           run.status_type === 'terrain' ? 'badge-terrain' :
                           run.status_type === 'relative' ? 'badge-warning' :
                           run.status_type === 'georeferenced' ? 'badge-warning' :
                           run.status_type === 'rejected' ? 'badge-danger' : 'badge-running';

        card.innerHTML = `
          <div class="run-card-header">
            <span class="run-name" title="${run.run_id}">${run.run_id}</span>
            <span class="run-badge ${badgeClass}">${run.badge || 'Processing'}</span>
          </div>
          <div class="run-details">
            <span>${run.badge || 'Processing'}</span>
            <span>&bull;</span>
            <span>${dateStr}</span>
          </div>
        `;

        card.addEventListener('click', () => {
          selectRun(run.run_id, run.has_model);
        });

        runListContainer.appendChild(card);

        if (isTarget && !autoSelected) {
          selectRun(run.run_id, run.has_model);
          autoSelected = true;
        }
      });

      // If no preferred target was set/found, auto-load the newest run that has a 3D model
      if (!autoSelected && !window.currentRunId) {
        const firstUsable = runs.find(r => r.has_model);
        if (firstUsable) {
          selectRun(firstUsable.run_id, true);
        }
      }
    } catch (err) {
      runListContainer.innerHTML = `<div class="empty-state" style="color:var(--danger)">Failed to load projects: ${err.message}</div>`;
    }
  }

  async function loadAccuracyReport(runId) {
    try {
      const res = await fetch(`/api/runs/${runId}`);
      const m = await res.json();
      reportSection.style.display = 'block';

      const acc = m.accuracy || {};
      const stages = m.stages || {};
      const nDense = stages.dense?.metrics?.n_dense_points || acc.n_dense_points;
      const pts = nDense ? Number(nDense).toLocaleString() + ' pts' : '—';
      const crs = acc.crs || 'LOCAL_RELATIVE';
      const isGeoref = crs !== 'LOCAL_RELATIVE' && stages.georef?.status === 'ok';
      const gpsLabel = isGeoref ? `Aligned (${crs})` : 'Relative / Unaligned';
      const rmseLabel = acc.alignment_rmse_m != null ? `${acc.alignment_rmse_m.toFixed(2)} m` : '—';

      accuracyReportEl.innerHTML = `
        <div class="report-row"><span class="report-label">3D Points</span><span class="report-value">${pts}</span></div>
        <div class="report-row"><span class="report-label">Georef CRS</span><span class="report-value">${gpsLabel}</span></div>
        <div class="report-row"><span class="report-label">Alignment RMSE</span><span class="report-value">${rmseLabel}</span></div>
      `;
    } catch (e) {
      reportSection.style.display = 'none';
    }
  }

  async function renderDownloadLinks(runId) {
    try {
      const res = await fetch(`/api/runs/${runId}`);
      const m = await res.json();
      const exportOutputs = m.stages?.export?.outputs || {};
      downloadSection.style.display = 'block';

      const links = [];
      links.push(`<a class="dl-btn dl-btn-primary" href="/api/runs/${runId}/report.html" target="_blank">Full Report (HTML)</a>`);
      if (exportOutputs.model_glb) {
        links.push(`<a class="dl-btn" href="/api/runs/${runId}/model.glb" download>3D Model (.glb)</a>`);
      }
      if (exportOutputs.model_alt_glb) {
        const variant = (exportOutputs.model_alt_label || 'alternate').replace(/_/g, ' ');
        links.push(`<a class="dl-btn" href="/api/runs/${runId}/model_alt.glb" download>3D Model — ${variant} texture (.glb)</a>`);
      }
      if (exportOutputs.cloud_laz) {
        links.push(`<a class="dl-btn" href="/api/runs/${runId}/cloud.laz" download>Point Cloud (.laz)</a>`);
      }
      if (exportOutputs.ortho_tif) {
        links.push(`<a class="dl-btn" href="/api/runs/${runId}/orthomosaic.tif" download>2D Aerial Map (.tif)</a>`);
      }
      if (exportOutputs.dsm_tif) {
        links.push(`<a class="dl-btn" href="/api/runs/${runId}/dsm.tif" download>Surface Elevation (.tif)</a>`);
      }
      if (exportOutputs.dtm_tif) {
        links.push(`<a class="dl-btn" href="/api/runs/${runId}/dtm.tif" download>Terrain Elevation (.tif)</a>`);
      }
      if (exportOutputs.trajectory_kml) {
        links.push(`<a class="dl-btn" href="/api/runs/${runId}/trajectory.kml" download>Flight Path (.kml)</a>`);
      }

      downloadLinksEl.innerHTML = links.join('');
    } catch (e) {
      downloadSection.style.display = 'none';
    }
  }

  if (btnRefreshRuns) btnRefreshRuns.addEventListener('click', fetchRuns);

  fetchRuns();
  window.fetchRuns = fetchRuns;
});
