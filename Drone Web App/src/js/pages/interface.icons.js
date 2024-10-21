/**
 *
 * Icons
 *
 * Interface.Content.Icons.CSLineIcons, Interface.Content.Icons.CSLineInterfaceIcons, Interface.Content.Icons.BootstrapIcons page content scripts. Initialized from scripts.js file.
 *
 * @param {string} skylynxInterfaceContainerId Container id of skylynx interface icons
 * @param {string} skylynxInterfaceInputId Input id for skylynx interface icons
 * @param {string} skylynxCommerceContainerId Container id of skylynx commerce icons
 * @param {string} skylynxCommerceInputId Input id for skylynx commerce icons
 * @param {string} skylynxMedicalContainerId Container id of skylynx medical icons
 * @param {string} skylynxMedicalInputId Input id for skylynx medical icons
 * @param {string} skylynxLearningContainerId Container id of skylynx learning icons
 * @param {string} skylynxLearningInputId Input id for skylynx learning icons
 * @param {string} bootstrapContainerId Container id of bootstrap
 * @param {string} bootstrapInputId Input id for bootstrap
 * @param {string} datapath Path for the data json file
 *
 */

class Icons {
  get options() {
    return {
      skylynxInterfaceContainerId: 'skylynxInterfaceIconsContainer',
      skylynxInterfaceInputId: 'skylynxInterfaceIconsSearch',
      skylynxCommerceContainerId: 'skylynxCommerceIconsContainer',
      skylynxCommerceInputId: 'skylynxCommerceIconsSearch',
      skylynxMedicalContainerId: 'skylynxMedicalIconsContainer',
      skylynxMedicalInputId: 'skylynxMedicalIconsSearch',
      skylynxLearningContainerId: 'skylynxLearningIconsContainer',
      skylynxLearningInputId: 'skylynxLearningIconsSearch',
      bootstrapContainerId: 'bootstrapIconsContainer',
      bootstrapInputId: 'bootstrapIconsSearch',
      datapath: Helpers.UrlFix('json/icons.json'),
    };
  }

  constructor(options = {}) {
    this.settings = Object.assign(this.options, options);
    this._init();
  }

  _init() {
    Helpers.FetchJSON(this.settings.datapath, (data) => {
      this._data = data;
      this._initAfterLoad();
    });
  }

  _initAfterLoad() {
    if (document.getElementById(this.settings.skylynxInterfaceContainerId)) {
      new IconLibrary({
        containerId: this.settings.skylynxInterfaceContainerId,
        inputId: this.settings.skylynxInterfaceInputId,
        data: this._data.skylynxInterface,
        isSvg: true,
      });
      new skylynxIcons().replace();
    }
    if (document.getElementById(this.settings.skylynxCommerceContainerId)) {
      new IconLibrary({
        containerId: this.settings.skylynxCommerceContainerId,
        inputId: this.settings.skylynxCommerceInputId,
        data: this._data.skylynxCommerce,
        isSvg: true,
      });
      new skylynxIcons().replace();
    }
    if (document.getElementById(this.settings.skylynxMedicalContainerId)) {
      new IconLibrary({
        containerId: this.settings.skylynxMedicalContainerId,
        inputId: this.settings.skylynxMedicalInputId,
        data: this._data.skylynxMedical,
        isSvg: true,
      });
      new skylynxIcons().replace();
    }
    if (document.getElementById(this.settings.skylynxLearningContainerId)) {
      new IconLibrary({
        containerId: this.settings.skylynxLearningContainerId,
        inputId: this.settings.skylynxLearningInputId,
        data: this._data.skylynxLearning,
        isSvg: true,
      });
      new skylynxIcons().replace();
    }
    if (document.getElementById(this.settings.bootstrapContainerId)) {
      new IconLibrary({
        containerId: this.settings.bootstrapContainerId,
        inputId: this.settings.bootstrapInputId,
        data: this._data.bootstrap,
        isSvg: false,
      });
    }
  }
}

/**
 *
 * IconLibrary
 * Icon list and fuzzy search implementation.
 *
 * @param {string} containerId Container id to render icons
 * @param {string} inputId Input for search
 * @param {string} data Data that contains icons
 * @param {string} isSvg CsLine svg icons are used differenty with i tag
 *
 */
class IconLibrary {
  get options() {
    return {
      containerId: '',
      inputId: '',
      data: null,
    };
  }

  constructor(options = {}) {
    this.settings = Object.assign(this.options, options);
    this._init();
  }

  _init() {
    const options = {
      includeScore: true,
      keys: ['t', 'c'],
      threshold: 0.2,
    };

    this.fuse = new Fuse(this.settings.data, options);
    this.foundNothing =
      '<div class="col-12 small-gutter-col flex-grow-1 mw-100"> <div class="card h-100"> <div class="card-body text-center"><i class="mb-3 d-inline-block text-primary cs-warning-hexagon"></i><p class="mb-0">Nothing found!</p></div></div></div>';

    this._addIcons(this.settings.data);
    this._addListeners();
  }

  _addIcons(data) {
    const container = document.getElementById(this.settings.containerId);
    if (!container) {
      return;
    }
    container.innerHTML = '';
    if (data.length === 0) {
      container.insertAdjacentHTML('beforeend', this.foundNothing);
      return;
    }
    var htmlString = '';
    for (var i = 0; i < data.length; i++) {
      let iconName = data[i].c || data[i].item.c;
      if (this.settings.isSvg) {
        htmlString +=
          '<div class="col small-gutter-col"> <div class="card h-100"> <div class="card-body text-center"><i class="mb-3 d-inline-block text-primary" data-skylynx-icon="' +
          iconName +
          '" data-skylynx-size="20"></i><p class="text-medium text-muted mb-0">' +
          iconName +
          '</p></div></div></div>';
      } else {
        htmlString +=
          '<div class="col small-gutter-col"> <div class="card h-100"> <div class="card-body text-center"><i class="mb-3 d-inline-block text-primary icon-20 ' +
          iconName +
          '"></i><p class="text-medium text-muted mb-0">' +
          iconName +
          '</p></div></div></div>';
      }
    }
    container.insertAdjacentHTML('beforeend', htmlString);
    if (typeof skylynxIcons !== 'undefined') {
      new skylynxIcons().replace();
    }
  }

  _addListeners() {
    const search = document.getElementById(this.settings.inputId);
    if (search) {
      search.addEventListener('keyup', Helpers.Debounce(this._search.bind(this), 500).bind(this));
    }
  }

  _search() {
    const search = document.getElementById(this.settings.inputId);
    const value = search.value;
    if (value === '') {
      this._addIcons(this.settings.data);
      return;
    }
    const result = this.fuse.search(value);
    this._addIcons(result);
  }
}
