document.addEventListener("DOMContentLoaded", () => {

    let selectedFiles = [];
    let uploadMode = null;
    let polling = false;

    const elements = {
        themeToggle: document.getElementById("theme-toggle"),
        startBtn: document.getElementById("start-btn"),
        inputSingle: document.getElementById("file-input-single"),
        inputZip: document.getElementById("file-input-zip"),
        singleList: document.getElementById("single-file-list"),
        zipList: document.getElementById("zip-file-list"),
        progressStatus: document.getElementById("progress-status"),
        progressBar: document.getElementById("progress-bar"),
        systemStatus: document.getElementById("system-status"),
        configForm: document.getElementById("config-form")
    };

    // --------------------------------
    // THEME TOGGLE (optional backend support)
    // --------------------------------
    if (elements.themeToggle) {
        // Set initial icon
        elements.themeToggle.innerText =
            document.body.getAttribute("data-theme") === "light" ? "🌞" : "🌙";

        elements.themeToggle.onclick = async () => {
            try {
                const res = await fetch("/toggle_theme", { method: "POST" });
                if (res.ok) {
                    const data = await res.json();
                    document.body.setAttribute("data-theme", data.theme);

                    // Update icon dynamically
                    elements.themeToggle.innerText =
                        data.theme === "light" ? "🌞" : "🌙";
                }
            } catch {
                console.warn("Theme toggle unavailable");
            }
        };
    }



    // --------------------------------
    // RENDER FILE CHIPS
    // --------------------------------
    function renderFileChips(files, container) {

        container.innerHTML = "";

        files.forEach(file => {

            const chip = document.createElement("div");

            chip.className = "file-chip";

            chip.innerHTML = `
                <span>${file.name}</span>
                <button type="button">×</button>
            `;

            chip.querySelector("button").onclick = () => {

                selectedFiles = selectedFiles.filter(
                    f => f !== file
                );

                chip.remove();

                elements.startBtn.disabled =
                    selectedFiles.length === 0;
            };

            container.appendChild(chip);
        });
    }


    // --------------------------------
    // FILE INPUT HANDLERS
    // --------------------------------
    elements.inputSingle.onchange = (e) => {

        uploadMode = "single";

        selectedFiles = Array.from(
            e.target.files
        );

        elements.inputZip.value = "";

        elements.zipList.innerHTML = "";

        renderFileChips(
            selectedFiles,
            elements.singleList
        );

        elements.startBtn.disabled =
            selectedFiles.length === 0;
    };


    elements.inputZip.onchange = (e) => {

        uploadMode = "zip";

        selectedFiles = Array.from(
            e.target.files
        );

        elements.inputSingle.value = "";

        elements.singleList.innerHTML = "";

        renderFileChips(
            selectedFiles,
            elements.zipList
        );

        elements.startBtn.disabled =
            selectedFiles.length === 0;
    };


    // --------------------------------
    // START PIPELINE
    // --------------------------------
    elements.startBtn.onclick = async () => {

        if (!selectedFiles.length || !uploadMode)
            return;

        resetProgressUI();

        try {

            // -------------------------
            // STEP 1: Upload Files
            // -------------------------
            elements.progressStatus.innerText = "Uploading Files...";

            const formData = new FormData();

            formData.append(
                "upload_mode",
                uploadMode
            );

            if (uploadMode === "zip") {

                formData.append(
                    "zip_file",
                    selectedFiles[0]
                );

            } else {

                selectedFiles.forEach(file =>
                    formData.append(
                        "sql_files",
                        file
                    )
                );
            }

            const uploadRes =
                await fetch("/upload_files", {
                    method: "POST",
                    body: formData
                });

            const uploadData =
                await uploadRes.json();

            if (!uploadRes.ok)
                throw new Error(
                    uploadData.error ||
                    "Upload failed"
                );


            // -------------------------
            // STEP 2: Start Job
            // -------------------------
            elements.progressStatus.innerText = "Triggering Databricks Job...";

            const configData =
                new FormData(
                    elements.configForm
                );

            const payload = {

                source_dialect:
                    configData.get(
                        "source_dialect"
                    ),

                catalog:
                    configData.get(
                        "catalog"
                    ),

                schema:
                    configData.get(
                        "schema"
                    ),

                model_choice:
                    configData.get(
                        "model_choice"
                    )
            };

            const triggerRes =
                await fetch("/start_job", {

                    method: "POST",

                    headers: {
                        "Content-Type":
                        "application/json"
                    },

                    body: JSON.stringify(
                        payload
                    )
                });

            const triggerData =
                await triggerRes.json();

            if (!triggerRes.ok)
                throw new Error(
                    triggerData.error ||
                    "Job start failed"
                );


            elements.progressStatus.innerText = "Pipeline Running...";

            elements.startBtn.innerText =
                "Running...";


            // -------------------------
            // STEP 3: Poll Status
            // -------------------------
            await pollJobStatus();


        } catch (err) {

            showError(err.message);
        }
    };


    // --------------------------------
    // POLL JOB STATUS
    // --------------------------------
    async function pollJobStatus() {
        polling = true;

        while (polling) {
            await sleep(3000);

            const statusRes = await fetch("/job_status");
            const statusData = await statusRes.json();

            if (!statusRes.ok || statusData.error) {
                showError(statusData.error || "Failed to fetch job status");
                return;
            }

            // Update progress bar dynamically
            updateProgressBar(statusData.progress, statusData.state);

            if (statusData.completed) {
                polling = false;

                elements.progressBar.style.width = "100%";
                elements.progressStatus.innerText = "TRANSPILATION COMPLETED (100%)";

                elements.startBtn.innerText = "Completed";
                elements.startBtn.disabled = false;

                // Redirect to migration report after short delay
                setTimeout(() => {
                    window.location.href = "/migration_report";
                }, 1500);

                break;
            }
        }
    }



    // --------------------------------
    // UI HELPERS
    // --------------------------------
    function resetProgressUI() {

        elements.startBtn.disabled = true;

        elements.startBtn.innerText =
            "Uploading...";

        elements.progressBar.style.width =
            "0%";

        elements.progressStatus.innerText =
            "";

        elements.systemStatus.innerText = "System Ready"; 
    }


    function updateProgressBar(progress, state) {

        // Update width
        elements.progressBar.style.width = progress + "%";

        // Show RUNNING / TERMINATED / COMPLETED dynamically
        let displayText = "";

        if (state) {
            if (state === "TERMINATED") {
                displayText = "TRANSPILATION COMPLETED (" + progress + "%)";
            } else if (state === "SKIPPED" || state === "INTERNAL_ERROR") {
                displayText = "ERROR (" + progress + "%)";
            } else {
                displayText = state + " (" + progress + "%)";
            }
        } else {
            displayText = "Running (" + progress + "%)";
        }

        elements.progressStatus.innerText = displayText;
    }



    function showError(message) {

        alert("Pipeline Error: " + message);

        elements.systemStatus.innerText =
            "Error";

        elements.startBtn.disabled = false;

        elements.startBtn.innerText =
            "Start Transpilation Engine";
    }


    function sleep(ms) {

        return new Promise(
            resolve =>
                setTimeout(resolve, ms)
        );
    }

});