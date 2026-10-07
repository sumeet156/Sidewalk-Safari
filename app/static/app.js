const STORAGE_KEY = "sidewalk-safari-packs";
const form = document.querySelector("#safari-form");
const statusMessage = document.querySelector("#status");
const setup = document.querySelector("#setup");
const play = document.querySelector("#play");
const goScreen = document.querySelector("#go");
const savedList = document.querySelector("#saved-packs");
let activePack = null;
let missionIndex = 0;

function readSavedPacks() {
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    return Array.isArray(stored) ? stored : [];
  } catch (error) {
    console.error("Could not read saved safari packs.", error);
    return [];
  }
}

function showMission() {
  const mission = activePack.missions[missionIndex];
  document.querySelector("#pack-context").textContent =
    `${activePack.setting} · ${activePack.time_limit_min} minutes · age ${activePack.age_band}`;
  document.querySelector("#progress").textContent =
    `Mission ${missionIndex + 1} of ${activePack.missions.length}`;
  document.querySelector("#mission-title").textContent = mission.type.replaceAll("_", " ");
  document.querySelector("#mission-text").textContent = mission.text;
  document.querySelector("#mission-safety").textContent = mission.safety_note;
  document.querySelector("#next-button").textContent =
    missionIndex === activePack.missions.length - 1 ? "Finish safari" : "Next mission";
  setup.classList.add("hidden");
  goScreen.classList.add("hidden");
  play.classList.remove("hidden");
}

function startPack(pack) {
  activePack = pack;
  missionIndex = 0;
  statusMessage.textContent = pack.generation_note || "";
  showMission();
}

function renderSavedPacks() {
  savedList.replaceChildren();
  for (const pack of readSavedPacks()) {
    const item = document.createElement("li");
    item.className = "saved-item";
    const label = document.createElement("span");
    label.textContent = `${pack.setting} · ${pack.time_limit_min} min · age ${pack.age_band}`;
    const button = document.createElement("button");
    button.className = "secondary";
    button.type = "button";
    button.textContent = "Play";
    button.addEventListener("click", () => startPack(pack));
    item.append(label, button);
    savedList.append(item);
  }
  if (!savedList.children.length) {
    const empty = document.createElement("li");
    empty.className = "privacy-hint";
    empty.textContent = "Packs you save here stay in this browser.";
    savedList.append(empty);
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const createButton = document.querySelector("#create-button");
  createButton.disabled = true;
  createButton.textContent = "Creating safari…";
  statusMessage.textContent = "Gemma is making your safari on this computer. This can take a few minutes.";
  const values = Object.fromEntries(new FormData(form));
  values.time_limit_min = Number(values.time_limit_min);
  try {
    const response = await fetch("/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(values),
    });
    let data;
    try {
      data = await response.json();
    } catch {
      throw new Error("The app returned an unreadable response. Please try again.");
    }
    if (!response.ok) {
      throw new Error(data.detail || "Could not create a safari.");
    }
    startPack(data);
  } catch (error) {
    console.error("Safari generation failed.", error);
    statusMessage.textContent = `Could not create a safari: ${error.message || "Please try again."}`;
  } finally {
    createButton.disabled = false;
    createButton.textContent = "Create safari";
  }
});

document.querySelector("#next-button").addEventListener("click", () => {
  if (missionIndex < activePack.missions.length - 1) {
    missionIndex += 1;
    showMission();
    return;
  }
  play.classList.add("hidden");
  document.querySelector("#closing").textContent = activePack.closing;
  goScreen.classList.remove("hidden");
});

document.querySelector("#save-button").addEventListener("click", () => {
  const packs = readSavedPacks().filter((pack) => pack.pack_id !== activePack.pack_id);
  packs.unshift(activePack);
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(packs.slice(0, 20)));
    renderSavedPacks();
    statusMessage.textContent = "Pack saved on this device for offline use.";
  } catch (error) {
    console.error("Could not save safari pack.", error);
    statusMessage.textContent = "Could not save this pack in browser storage.";
  }
});

document.querySelector("#done-button").addEventListener("click", () => {
  goScreen.classList.add("hidden");
  setup.classList.remove("hidden");
});

renderSavedPacks();
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/service-worker.js").catch((error) => {
    console.error("Offline app shell could not be installed.", error);
  });
}
