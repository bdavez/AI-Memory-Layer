export function getStatusClass(status) {
  switch (status) {
    case "healthy":
      return "status-pill status-healthy";   // green
    case "warning":
      return "status-pill status-warning";   // pink
    case "busy":
      return "status-pill status-busy";      // orange/yellow
    case "unknown":
      return "status-pill status-unknown";   // grey
    case "dead":
      return "status-pill status-dead";      // red
    default:
      return "status-pill status-unknown";
  }
}

export function getStatusLabel(status) {
  switch (status) {
    case "healthy": return "Healthy";
    case "warning": return "Warning";
    case "busy":    return "Busy";
    case "unknown": return "Unknown";
    case "dead":    return "Offline";
    default:        return "Unknown";
  }
}
