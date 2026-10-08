let currentPlanId = null;
let currentRequest = null;
let reviewInProgress = false;

const travelForm = document.getElementById("travelForm");
const loadingSection = document.getElementById("loadingSection");
const resultSection = document.getElementById("resultSection");
const errorBox = document.getElementById("errorBox");
const errorMessage = document.getElementById("errorMessage");
const generateButton = document.getElementById("generateButton");

const rejectBox = document.getElementById("rejectBox");
const modifyBox = document.getElementById("modifyBox");
const reviewPanel = document.getElementById("reviewPanel");
const approvedPanel = document.getElementById("approvedPanel");

function showError(message) {
    errorMessage.textContent = message;
    errorBox.classList.remove("hidden");
}

function hideError() {
    errorBox.classList.add("hidden");
}

function setLoading(show, message = "AI agents are planning your trip...") {
    document.getElementById("loadingMessage").textContent = message;

    if (show) {
        loadingSection.classList.remove("hidden");
        generateButton.disabled = true;
    } else {
        loadingSection.classList.add("hidden");
        generateButton.disabled = false;
    }
}

function formatMoney(value) {
    if (value === undefined || value === null) return "—";

    return new Intl.NumberFormat("en-IN", {
        maximumFractionDigits: 0
    }).format(value);
}

function renderItinerary(draft) {
    if (!draft) {
        return `<p class="empty-message">No itinerary available.</p>`;
    }

    let html = "";

    if (draft.summary) {
        html += `
            <div class="trip-summary-banner">
                <span>✨</span>
                <div>
                    <small>TRIP OVERVIEW</small>
                    <h3>${draft.summary}</h3>
                </div>
            </div>
        `;
    }

    if (Array.isArray(draft.days)) {
        html += `<div class="days-container">`;

        draft.days.forEach(day => {
            html += `
                <article class="day-card">
                    <div class="day-header">
                        <div class="day-number">${day.day}</div>

                        <div>
                            <span>DAY ${day.day}</span>
                            <h3>${day.date || ""}</h3>
                        </div>
                    </div>

                    <div class="activity-grid">
                        <div class="activity-item">
                            <div class="activity-icon">☀️</div>
                            <div>
                                <span>Morning</span>
                                <p>${day.morning || "Flexible time"}</p>
                            </div>
                        </div>

                        <div class="activity-item">
                            <div class="activity-icon">🌤️</div>
                            <div>
                                <span>Afternoon</span>
                                <p>${day.afternoon || "Flexible time"}</p>
                            </div>
                        </div>

                        <div class="activity-item">
                            <div class="activity-icon">🌙</div>
                            <div>
                                <span>Evening</span>
                                <p>${day.evening || "Flexible time"}</p>
                            </div>
                        </div>
                    </div>

                    ${day.notes
                    ? `<div class="day-note">💡 ${day.notes}</div>`
                    : ""
                }
                </article>
            `;
        });

        html += `</div>`;
    }

    if (draft.budget) {
        const budget = draft.budget;
        const currency = currentRequest?.currency || "";

        html += `
            <div class="detail-section">
                <div class="detail-heading">
                    <span>💰</span>
                    <div>
                        <h3>Smart Budget Breakdown</h3>
                        <p>AI-assisted allocation for your trip.</p>
                    </div>
                </div>

                <div class="budget-grid">
                    <div class="budget-item">
                        <span>🏨 Lodging</span>
                        <strong>${currency} ${formatMoney(budget.lodging)}</strong>
                    </div>

                    <div class="budget-item">
                        <span>🍽️ Food</span>
                        <strong>${currency} ${formatMoney(budget.food)}</strong>
                    </div>

                    <div class="budget-item">
                        <span>🎟️ Activities</span>
                        <strong>${currency} ${formatMoney(budget.activities)}</strong>
                    </div>

                    <div class="budget-item">
                        <span>🚕 Local Transport</span>
                        <strong>${currency} ${formatMoney(budget.local_transport)}</strong>
                    </div>

                    <div class="budget-item">
                        <span>🛡️ Buffer</span>
                        <strong>${currency} ${formatMoney(budget.buffer)}</strong>
                    </div>

                    <div class="budget-item highlight-budget">
                        <span>🎯 Target Total</span>
                        <strong>${currency} ${formatMoney(budget.target_total)}</strong>
                    </div>
                </div>
            </div>
        `;
    }

    if (Array.isArray(draft.packing) && draft.packing.length) {
        html += `
            <div class="detail-section">
                <div class="detail-heading">
                    <span>🎒</span>
                    <div>
                        <h3>Smart Packing List</h3>
                        <p>Recommended items based on your trip.</p>
                    </div>
                </div>

                <div class="packing-list">
                    ${draft.packing
                .map(
                    item => `
                                <span class="packing-chip">
                                    ✓ ${item}
                                </span>
                            `
                )
                .join("")}
                </div>
            </div>
        `;
    }

    return html;
}

function updateResult(data) {
    resultSection.classList.remove("hidden");

    document.getElementById("resultDestination").textContent =
        currentRequest?.destination
            ? `${currentRequest.destination} Travel Plan`
            : "Your Travel Plan";

    document.getElementById("summaryDates").textContent =
        currentRequest
            ? `${currentRequest.start_date} → ${currentRequest.end_date}`
            : "—";

    document.getElementById("summaryTravelers").textContent =
        currentRequest?.travelers ?? "—";

    document.getElementById("summaryBudget").textContent =
        currentRequest
            ? `${currentRequest.currency} ${currentRequest.budget_min.toLocaleString()} – ${currentRequest.budget_max.toLocaleString()}`
            : "—";

    document.getElementById("summaryRevisions").textContent =
        data.revision_count ?? 0;

    const status = data.status || "unknown";

    document.getElementById("planStatus").textContent =
        status === "awaiting_review"
            ? "Awaiting Review"
            : status === "approved"
                ? "Approved"
                : status;

    const content = document.getElementById("itineraryContent");
    content.innerHTML = renderItinerary(data.draft || {});

    if (status === "approved") {
        reviewPanel.classList.add("hidden");
        approvedPanel.classList.remove("hidden");
    } else {
        reviewPanel.classList.remove("hidden");
        approvedPanel.classList.add("hidden");
    }

    resultSection.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });
}

travelForm.addEventListener("submit", async event => {
    event.preventDefault();
    hideError();

    const interests = [
        ...document.querySelectorAll(
            '.interest-option input[type="checkbox"]:checked'
        )
    ].map(item => item.value);

    if (interests.length === 0) {
        showError("Please select at least one travel interest.");
        return;
    }

    const requestBody = {
        destination: document.getElementById("destination").value.trim(),
        start_date: document.getElementById("startDate").value,
        end_date: document.getElementById("endDate").value,
        budget_min: Number(document.getElementById("budgetMin").value),
        budget_max: Number(document.getElementById("budgetMax").value),
        interests,
        travelers: Number(document.getElementById("travelers").value),
        currency: document.getElementById("currency").value
    };

    if (requestBody.end_date < requestBody.start_date) {
        showError("End date cannot be before start date.");
        return;
    }

    if (requestBody.budget_max < requestBody.budget_min) {
        showError("Maximum budget must be greater than minimum budget.");
        return;
    }

    currentRequest = requestBody;
    currentPlanId = null;

    resultSection.classList.add("hidden");

    setLoading(
        true,
        "Research Agent is searching destination information..."
    );

    try {
        const response = await fetch("/plan", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(requestBody)
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail
                    ? JSON.stringify(data.detail)
                    : "Unable to create travel plan."
            );
        }

        currentPlanId = data.plan_id;
        updateResult(data);
    } catch (error) {
        showError(error.message);
    } finally {
        setLoading(false);
    }
});

document.getElementById("rejectButton").addEventListener("click", () => {
    rejectBox.classList.toggle("hidden");
    modifyBox.classList.add("hidden");
});

document.getElementById("modifyButton").addEventListener("click", () => {
    modifyBox.classList.toggle("hidden");
    rejectBox.classList.add("hidden");
});

document.getElementById("approveButton").addEventListener("click", async () => {
    if (!currentPlanId || reviewInProgress) return;

    reviewInProgress = true;
    hideError();

    setLoading(
        true,
        "Submitting your approval and finalizing the itinerary..."
    );

    try {
        const response = await fetch(`/plan/${currentPlanId}/review`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                action: "approve"
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Unable to approve plan.");
        }

        const finalResponse = await fetch(
            `/plan/${currentPlanId}/final`
        );

        const finalData = await finalResponse.json();

        if (!finalResponse.ok) {
            throw new Error(
                finalData.detail || "Unable to load final plan."
            );
        }

        updateResult({
            ...data,
            draft: finalData.plan,
            status: "approved"
        });
    } catch (error) {
        showError(error.message);
    } finally {
        reviewInProgress = false;
        setLoading(false);
    }
});

document.getElementById("submitReject").addEventListener("click", async () => {
    if (!currentPlanId || reviewInProgress) return;

    const feedback =
        document.getElementById("rejectFeedback").value.trim();

    if (!feedback) {
        showError("Please enter revision feedback.");
        return;
    }

    reviewInProgress = true;
    hideError();

    setLoading(
        true,
        "Planner Agent is revising your itinerary using your feedback..."
    );

    try {
        const response = await fetch(`/plan/${currentPlanId}/review`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                action: "reject",
                feedback
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail || "Unable to revise travel plan."
            );
        }

        rejectBox.classList.add("hidden");
        document.getElementById("rejectFeedback").value = "";

        updateResult(data);
    } catch (error) {
        showError(error.message);
    } finally {
        reviewInProgress = false;
        setLoading(false);
    }
});

document.getElementById("submitModify").addEventListener("click", async () => {
    if (!currentPlanId || reviewInProgress) return;

    const field =
        document.getElementById("modifyField").value.trim();

    const value =
        document.getElementById("modifyValue").value.trim();

    if (!field || !value) {
        showError(
            "Please enter both the section to modify and your requested change."
        );
        return;
    }

    reviewInProgress = true;
    hideError();

    setLoading(
        true,
        "Planner Agent is applying your requested modification..."
    );

    try {
        const response = await fetch(`/plan/${currentPlanId}/review`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                action: "modify",
                modifications: {
                    [field]: value
                }
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail || "Unable to modify travel plan."
            );
        }

        modifyBox.classList.add("hidden");
        document.getElementById("modifyField").value = "";
        document.getElementById("modifyValue").value = "";

        updateResult(data);
    } catch (error) {
        showError(error.message);
    } finally {
        reviewInProgress = false;
        setLoading(false);
    }
});