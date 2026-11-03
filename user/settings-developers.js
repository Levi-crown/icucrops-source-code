(function registerSettingsDevelopersSection(global) {
  const registry = global.settingsSectionRegistry || (global.settingsSectionRegistry = {});

  registry.developers = {
    path: "./settings-developers.html",
    render(template) {
      const getAvatarStyle = (developer) => {
        if (!developer.imagePath) {
          return "";
        }

        const cssVars = [];

        if (developer.imageScale) {
          cssVars.push(`--developer-photo-scale: ${developer.imageScale};`);
        }

        if (developer.imagePosition) {
          cssVars.push(`--developer-photo-position: ${developer.imagePosition};`);
        }

        return cssVars.length ? ` style="${escapeHtml(cssVars.join(" "))}"` : "";
      };

      const renderDeveloperCard = (developer, variant = "member") => `
        <article class="developer-card developer-card--${variant}">
          ${variant === "leader" ? '<span class="developer-card__badge">Group Leader</span>' : ""}
          <div class="developer-card__meta">
            <div class="developer-card__avatar ${developer.imagePath ? "developer-card__avatar--photo" : ""}"${getAvatarStyle(developer)}>
              ${
                developer.imagePath
                  ? `<img src="${escapeHtml(developer.imagePath)}" alt="${escapeHtml(developer.name)}" />`
                  : escapeHtml(developer.avatar)
              }
            </div>
            <div class="developer-card__copy">
              <h4 class="developer-card__name">${escapeHtml(developer.name)}</h4>
              <p class="developer-card__role">${escapeHtml(developer.role)}</p>
              <p class="developer-card__description">${escapeHtml(developer.description)}</p>
            </div>
          </div>
        </article>
      `;

      const leader = DEVELOPERS.find((developer) =>
        developer.role.toLowerCase() === "leader" || developer.name.toLowerCase().includes("shiela")
      ) || DEVELOPERS[0];
      const members = DEVELOPERS.filter((developer) => developer !== leader);
      const leaderCard = renderDeveloperCard(leader, "leader");
      const memberCards = members.map((developer) => renderDeveloperCard(developer)).join("");

      return replaceTemplateTokens(template, {
        DEVELOPER_LEADER_CARD: leaderCard,
        DEVELOPER_MEMBER_CARDS: memberCards,
      });
    },
  };

  global.settingsDevelopersTemplate = function settingsDevelopersTemplate() {
    return renderExternalTemplate("developers");
  };
})(window);
