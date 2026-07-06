async function loadUsers() {
  const users = await apiMemoryListUsers();
  const sel = document.getElementById("md-user-select");
  sel.innerHTML = "";

  users.forEach(u => {
    const opt = document.createElement("option");
    opt.value = u;
    opt.textContent = u;
    sel.appendChild(opt);
  });

  if (users.length > 0) {
    sel.value = users[0];
    loadUserData(users[0]);
  }
}

document.getElementById("md-create-user").addEventListener("click", async () => {
  const name = prompt("Enter new user ID:");
  if (!name) return;

  await apiMemoryCreateUser(name);
  await loadUsers();
});