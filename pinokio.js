module.exports = {
  title: "Open Wearables Local",
  description: "Personal health data aggregation platform. Sync data from Apple Health and other wearable devices to your own local database.",
  icon: "icon.png",
  menu: [
    {
      text: "Install",
      href: "install.js",
      icon: "fa-solid fa-download"
    },
    {
      text: "Start",
      href: "start.js",
      icon: "fa-solid fa-play"
    },
    {
      text: "Stop",
      href: "stop.js",
      icon: "fa-solid fa-stop"
    },
    {
      text: "Open Dashboard",
      href: "http://localhost:3000",
      icon: "fa-solid fa-globe"
    },
    {
      text: "Open API Docs",
      href: "http://localhost:8000/docs",
      icon: "fa-solid fa-book"
    },
    {
      text: "Configure Providers",
      href: "configure.js",
      icon: "fa-solid fa-gear"
    },
    {
      text: "Reset Database",
      href: "reset.js",
      icon: "fa-solid fa-rotate-left"
    }
  ]
};

