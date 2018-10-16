Koe: open-source software to visualise, segment and classify acoustic units in animal vocalisations
===

## What is it?
Koe is an application for classifying and analysing animal vocalisations.
Koe offers bulk-labelling of units via interactive ordination plots, as well as visualisation and playback, segmentation, measurement, data filtering/exporting and new tools for analysing repertoire and sequence structure -- all in an integrated database.

![**Koe**'s unit table is designed for classifying, annotating and filtering units.  Each unit row contains a spectrogram which becomes enlarged during mouse-over.  Unit audio plays when a spectrogram is clicked. The table can be sorted/filtered by any columns. Sorting by the Similarity Index column arranges units by spectral similarity for expedited labelling. Example data are New Zealand bellbird *Anthornis melanura* song units.](docs/syllable-view.png)

![**Segment songs into units** view, showing a song being segmented into units. The interface for partitioning recordings into songs is similar. Units are manually segmented by dragging over the spectrogram; unit endpoints can be re-adjusted at any time. A selection box can be clicked for playback. Spectrogram zoom, contrast and colourmap can be adjusted. Units can be labelled, or comments given. This example is a female New Zealand bellbird (*Anthornis melanura*) song from Hauturu.](docs/segmentation-view.png)

![*Koe*'s interactive ordination view allows the user to encircle groups of points on the plot with the lasso tool, to view their spectrograms and hear their audio. Mousing over a point in a selection highlights the corresponding spectrogram in the left-hand panel. Selections can be labelled in bulk directly on the plot or opened as a unit table to view detailed unit information. The user can zoom, toggle the visibility of classes, and export the plot as a vector graphic. This example shows a t-SNE ordination of 7189 units of male and female New Zealand bellbird **Anthornis melanura** song on Tiritiri Matangi Island.](docs/Ordination-view.png)

## How to install, run and deploy this on your own?

I recommend using the official website at https://koe.io.ac.nz. However if you want to run Koe on your own computer/server, here's how:

[Install](docs/INSTALL.md)

[Run](docs/RUN.md)

[Upgrade](docs/UPGRADE.md)

[Deploy](docs/DEPLOY.md)

## Licence
<a rel="license" href="http://creativecommons.org/licenses/by-nc-sa/4.0/"><img alt="Creative Commons License" style="border-width:0" src="https://i.creativecommons.org/l/by-nc-sa/4.0/88x31.png" /></a><br />This work is licensed under a <a rel="license" href="http://creativecommons.org/licenses/by-nc-sa/4.0/">Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License</a>.

> TL;DR    
>  - You are allowed to copy, use and distribute this work free of charge.    
>  - You are allowed to change the source code and distribute that, given that you don't change the licence.    
>  - No commercial use is allowed, for both this work and any derivative thereof.    


Read the full [LICENCE](LICENCE.md) here

Contact us if you want a different licence option.

## Copyright
Copyright (c) 2013-9999 Yukio Fukuzawa. All rights reserved.
