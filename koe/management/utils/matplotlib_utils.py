from colorsys import hls_to_rgb

import colorlover as cl
import numpy as np
from PIL import Image
from scipy.cluster import hierarchy

from koe.utils import PAGE_CAPACITY


def set_size(w, h, ax=None):
    import matplotlib.pyplot as plt

    if not ax:
        ax = plt.gca()
    left = ax.figure.subplotpars.left
    r = ax.figure.subplotpars.right
    t = ax.figure.subplotpars.top
    b = ax.figure.subplotpars.bottom
    figw = float(w) / (r - left)
    figh = float(h) / (t - b)
    ax.figure.set_size_inches(figw, figh)


def scatter_plot_with_highlighted_clusters(
    highlighted_cls_names, syl_cls_names, syl_ids, ordination_data, pdf=None, fig=None
):
    """
    Plot a scatter plot with all datapoints, those which are highlighted are displayed in colour and bigger size
    The positions of the datapoints are exactly the same as displayed in Koe's ordination view
    :param highlighted_cls_names: list of classes to highlight
    :param syl_cls_names: array of class names corresponding to each datapoint
    :param syl_ids: array of syllable IDs corresponding to each datapoint
    :param ordination_data:
    :param pdf: None to display inline, or instance pf PdfPages to write to a pdf file
    :return:
    """
    import matplotlib.pyplot as plt

    nCategoricalColours = 11
    nClasses = len(highlighted_cls_names) + 1
    if nClasses <= nCategoricalColours:
        #     colours = cl.to_numeric(cl.scales[str(nClasses)]['div']['Spectral'])
        colours = cl.to_numeric(cl.scales[str(nClasses)]["div"]["Spectral"])
    else:
        colours = cl.to_numeric(cl.interp(cl.scales[str(nCategoricalColours)]["div"]["Spectral"], nClasses))
    colours = (np.array(colours) / 255.0).tolist()

    # Display clustering:
    if fig is None:
        fig = plt.figure(figsize=(18, 18))
    ax = fig.gca()

    syl_inds_unused = np.ones((len(syl_ids),))
    for cls, colour in zip(highlighted_cls_names, colours[1:]):
        syl_inds = np.where(syl_cls_names == cls)
        syl_inds_unused[syl_inds] = 0
        x = ordination_data[syl_inds, 0]
        y = ordination_data[syl_inds, 1]
        c = colour

        ax.scatter(
            x=x,
            y=y,
            s=100,
            c=[c],
            edgecolors=(0, 0, 0),
            linewidths=1,
            label=cls,
            alpha=0.5,
        )

    syl_inds_unused = np.where(syl_inds_unused == 1)
    x = ordination_data[syl_inds_unused, 0]
    y = ordination_data[syl_inds_unused, 1]
    c = colours[0]

    ax.scatter(x=x, y=y, s=10, c=[c], linewidths=0, label="other", alpha=0.2)
    plt.legend(loc=2)

    if pdf:
        pdf.savefig(fig)
        plt.close()
    else:
        plt.show()


def show_highlighed_cls_syllables(highlighted_cls_names, syl_cls_names, syl_tids, pdf=None):
    """
    For each highlighted class, display all or some syllables. Can be row
    :param highlighted_cls_names: list of classes to highlight
    :param syl_cls_names: array of class names corresponding to each datapoint
    :param syl_tids: array of syllable TIDs corresponding to each datapoint
    :param pdf: None to display inline, or instance pf PdfPages to write to a pdf file
    :return:
    """
    import matplotlib.pyplot as plt

    fig_w_in = 18
    dpi = 72
    fig_w_px = int(fig_w_in * dpi)

    final_imgs_combs = []
    subplot_cols = []
    current_subplot_col = 0
    for cls in highlighted_cls_names:
        subplot_cols.append([current_subplot_col])

        syl_inds = np.where(syl_cls_names == cls)
        selected_tids = syl_tids[syl_inds]
        img_dir = "user_data/spect/syllable"
        selected_syl_imgpth = [img_dir + str(tid // PAGE_CAPACITY) + "/{}.png".format(tid) for tid in selected_tids]

        images = [Image.open(i) for i in selected_syl_imgpth]
        widths, heights = zip(*(i.size for i in images))
        max_height = max(heights)
        total_height = max_height
        offset = 20
        imgs_combs = []
        imgs_comb = np.full((max_height, fig_w_px, 3), 255, dtype=np.uint8)
        current_col = 0
        col_count = 1
        for img in images:
            img_arr = np.asarray(img)
            width, height = img.size
            if current_col + width > fig_w_px:
                imgs_combs.append(imgs_comb)
                col_count += 1
                if col_count <= 2:
                    imgs_comb = np.full((max_height, fig_w_px, 3), 255, dtype=np.uint8)
                    total_height += max_height + offset
                    current_subplot_col += 1
                    current_col = 0
                else:
                    imgs_comb = None

            if col_count > 2:
                break
            imgs_comb[:, current_col : current_col + width] = img_arr
            current_col = current_col + width + offset

        if imgs_comb is not None:
            imgs_combs.append(imgs_comb)
        final_imgs_comb = np.full((total_height, fig_w_px, 3), 255, dtype=np.uint8)

        current_subplot_col += 1
        subplot_cols[-1].append(current_subplot_col)

        current_row = 0
        for imgs_comb in imgs_combs:
            final_imgs_comb[current_row : current_row + max_height, :] = imgs_comb
            current_row = current_row + max_height + offset

        final_imgs_comb = Image.fromarray(final_imgs_comb)
        final_imgs_combs.append(final_imgs_comb)

    max_height = max([x.size[1] for x in final_imgs_combs])
    total_height_px = max_height * len(highlighted_cls_names)

    total_height_in = total_height_px / dpi

    fig = plt.figure(figsize=(fig_w_in, total_height_in))
    for i, cls in enumerate(highlighted_cls_names):
        subplot_col = subplot_cols[i]
        start_col = subplot_col[0]
        span = subplot_col[1] - start_col
        ax = plt.subplot2grid((current_subplot_col, 1), (start_col, 0), rowspan=span)
        #         print('plt.subplot2grid(({}, 1), ({}, 0), rowspan={})'.format(current_subplot_col, start_col, span))
        final_imgs_comb = final_imgs_combs[i]
        ax.imshow(np.asarray(final_imgs_comb))
        ax.axis("off")
        ax.set_title(cls)

    if pdf:
        pdf.savefig(fig)
        plt.close()
    else:
        plt.show()


def show_highlighed_syllables(highlighted_syls_name, highlighted_syl_tids, pdf=None):
    """
    For each highlighted class, display all or some syllables. Can be row
    :param highlighted_cls_names: list of classes to highlight
    :param syl_cls_names: array of class names corresponding to each datapoint
    :param syl_tids: array of syllable TIDs corresponding to each datapoint
    :param pdf: None to display inline, or instance pf PdfPages to write to a pdf file
    :return:
    """
    import matplotlib.pyplot as plt

    fig_w_in = 18
    dpi = 72
    fig_w_px = int(fig_w_in * dpi)

    row_count = 1

    img_dir = "user_data/spect/syllable"
    selected_syl_imgpth = [img_dir + str(tid // PAGE_CAPACITY) + "/{}.png".format(tid) for tid in highlighted_syl_tids]

    images = [Image.open(i) for i in selected_syl_imgpth]
    widths, heights = zip(*(i.size for i in images))
    max_height = max(heights)
    # total_height = max_height
    offset = 20
    imgs_combs = []
    imgs_comb = np.full((max_height, fig_w_px, 3), 255, dtype=np.uint8)
    current_col = 0
    # col_count = 1
    for img in images:
        img_arr = np.asarray(img)
        width, height = img.size
        if current_col + width > fig_w_px:
            imgs_combs.append(imgs_comb)
            # col_count += 1
            # if col_count <= 2:
            imgs_comb = np.full((max_height, fig_w_px, 3), 255, dtype=np.uint8)
            row_count += 1
            current_col = 0
            # else:
            #     imgs_comb = None

        # if col_count > 2:
        #     break
        imgs_comb[:, current_col : current_col + width] = img_arr
        current_col = current_col + width + offset

    # if imgs_comb is not None:
    imgs_combs.append(imgs_comb)
    total_height = max_height + (max_height + offset) * (len(imgs_combs) - 1)
    final_imgs_comb = np.full((total_height, fig_w_px, 3), 255, dtype=np.uint8)

    current_row = 0
    for imgs_comb in imgs_combs:
        final_imgs_comb[current_row : current_row + max_height, :] = imgs_comb
        current_row = current_row + max_height + offset

    final_imgs_comb = Image.fromarray(final_imgs_comb)
    total_height_px = final_imgs_comb.size[1]

    total_height_in = total_height_px / dpi

    fig = plt.figure(figsize=(fig_w_in, total_height_in))

    ax = plt.gca()
    ax.imshow(np.asarray(final_imgs_comb))
    ax.axis("off")
    ax.set_title(highlighted_syls_name)

    if pdf:
        pdf.savefig(fig)
        plt.close()
    else:
        plt.show()


def to_hex(scale):
    """
    Convert an hsl, numeric or rgb color to string hex color. ie,
    [ "hsl(360,100,100)", "hsl(360,100,100)", "hsl(360,100,100)" ] -->
    [ "#FFFFFF", "#FFFFFF", "#FFFFFF" ]
    """
    s_t = cl.scale_type(scale)

    if s_t == "hex":
        return scale
    elif s_t == "numeric":
        return ["#%02x%02x%02x" % tuple(map(int, s)) for s in cl.to_numeric(scale)]
    elif s_t == "rgb":
        return ["#%02x%02x%02x" % tuple(map(int, s)) for s in cl.to_numeric(scale)]
    elif s_t == "hsl":
        return ["#%02x%02x%02x" % tuple(map(int, s)) for s in cl.to_numeric(scale)]


def to_numeric(scale):
    """
    Converts scale of rgb or hsl strings to list of tuples with rgb integer values. ie,
        [ "rgb(255, 255, 255)", "rgb(255, 255, 255)", "rgb(255, 255, 255)" ] -->
        [ (255, 255, 255), (255, 255, 255), (255, 255, 255) ]
    """
    numeric_scale = []
    s_t = cl.scale_type(scale)
    if s_t == "rgb":
        for s in scale:
            s = s[s.find("(") + 1 : s.find(")")].replace(" ", "").split(",")
            numeric_scale.append((float(s[0]), float(s[1]), float(s[2])))
    elif s_t == "hsl":
        for s in scale:
            s = s[s.find("(") + 1 : s.find(")")].replace(" ", "").replace("%", "").split(",")
            hls_h = float(s[0]) / 360.0
            hls_l = float(s[2]) / 100.0
            hls_s = float(s[1]) / 100.0
            rgb = hls_to_rgb(hls_h, hls_l, hls_s)
            numeric_scale.append((int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255)))
    elif s_t == "numeric":
        numeric_scale = scale
    return numeric_scale


def get_colours(n_classes, rettype="numeric255"):
    n_categorical_colours = 11

    if n_classes <= n_categorical_colours:
        #     colours = cl.to_numeric(cl.scales[str(nClasses)]['div']['Spectral'])
        colours = to_numeric(cl.scales[str(n_classes)]["div"]["Spectral"])
    else:
        colours = to_numeric(cl.interp(cl.scales[str(n_categorical_colours)]["div"]["Spectral"], n_classes))

    if rettype == "numeric255":
        return colours
    if rettype == "numeric1":
        return (np.array(colours) / 255.0).tolist()
    if rettype == "hex":
        return to_hex(colours)

    raise Exception("Unknown type {}".format(rettype))


def plot_dendrogram(tree, figname, label_arr, clusters=None, orientation="right", pdf=None, fig=None):
    import matplotlib.pyplot as plt

    if fig is None:
        fig = plt.figure(figsize=(18, 18))
    ax = fig.gca()
    ax.set_title(figname)
    nleaves = len(tree)

    if clusters is None:
        link_color_func = None
    else:
        clusters = [x for x in clusters if len(x) > 1]
        nclusters = len(clusters)
        cluster_map = {}
        for cind, c in enumerate(clusters):
            for ind in c:
                cluster_map[ind] = cind

        colours = get_colours(nclusters, "hex")
        link_cols = {}
        for i, i12 in enumerate(tree[:, :2].astype(int)):
            cs = []
            for x in i12:
                if x > nleaves:
                    c = link_cols[x]
                else:
                    if x in cluster_map:
                        c = colours[cluster_map[x]]
                    else:
                        c = "#000000"
                cs.append(c)
            link_cols[i + 1 + nleaves] = cs[0] if cs[0] == cs[1] else "#000000"

        def link_color_func(x):
            return link_cols[x]

    hierarchy.dendrogram(tree, labels=label_arr, orientation=orientation, link_color_func=link_color_func)
    if pdf:
        pdf.savefig(fig)
        plt.close()
    else:
        plt.show()
